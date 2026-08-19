from dataclasses import replace
from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import (
    GeneratedMediaIngestionError,
    GeneratedMediaIngestionService,
    GeneratedMediaPersistenceService,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.provider_execution import (
    DurableExecutionEvent,
    DurableExecutionJob,
    ProviderExecutionOutput,
    ProviderExecutionState,
)
from vscs.domain.generated_media import GeneratedMediaFile, GeneratedMediaKind, GeneratedMediaState

NOW = datetime(2026, 8, 18, 21, 0, tzinfo=UTC)


class InMemoryGeneratedMediaRepository:
    def __init__(self) -> None:
        self.items = {}

    def get(self, media_id: str):
        return self.items.get(media_id)

    def save(self, media):
        self.items[media.media_id] = media
        return media

    def list_for_production(self, production_id: str):
        return tuple(
            item for item in self.items.values() if item.scope.production_id == production_id
        )

    def list_for_episode(self, production_id: str, episode_id: str):
        return tuple(
            item
            for item in self.items.values()
            if item.scope.production_id == production_id and item.scope.episode_id == episode_id
        )

    def list_for_scene(self, production_id: str, episode_id: str, scene_id: str):
        return tuple(
            item
            for item in self.items.values()
            if item.scope.production_id == production_id
            and item.scope.episode_id == episode_id
            and item.scope.scene_id == scene_id
        )

    def list_for_shot(self, production_id: str, episode_id: str, scene_id: str, shot_id: str):
        return tuple(
            item
            for item in self.items.values()
            if item.scope.production_id == production_id
            and item.scope.episode_id == episode_id
            and item.scope.scene_id == scene_id
            and item.scope.shot_id == shot_id
        )

    def list_for_task(self, production_task_id: str):
        return tuple(
            item
            for item in self.items.values()
            if item.scope.production_task_id == production_task_id
        )

    def list_for_execution(self, execution_id: str):
        return tuple(
            item for item in self.items.values() if item.provenance.execution_id == execution_id
        )


class RecordingFileStore:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def ingest(
        self, source_relative_path: str, destination_relative_path: str
    ) -> GeneratedMediaFile:
        self.calls.append((source_relative_path, destination_relative_path))
        return GeneratedMediaFile(
            relative_path=destination_relative_path,
            checksum_sha256="a" * 64,
            size_bytes=123,
        )


def _task(fingerprint: str = "authority-20-9") -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-9-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-9-001",
            revision=1,
            fingerprint=fingerprint,
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _execution(
    state: ProviderExecutionState = ProviderExecutionState.COMPLETED,
) -> DurableExecutionJob:
    return DurableExecutionJob(
        execution_id="PEX-PQ-20-9-PQE-20-9-A001",
        production_id="XORIX",
        task_id="PT-20-9-001",
        queue_id="PQ-20-9",
        entry_id="PQE-20-9",
        resource_id="GPU-01",
        worker_id="WORKER-01",
        lease_id="PLEASE-20-9",
        attempt_number=1,
        authority_fingerprint="authority-20-9",
        provider_id="LOCAL-COMFYUI-01",
        provider_job_id="prompt-20-9",
        render_request_id="REQ-20-9",
        workflow_id="video_production_engine_v7_1_4",
        state=state,
        created_at=NOW,
        updated_at=NOW,
        submitted_at=NOW,
        progress=1.0 if state is ProviderExecutionState.COMPLETED else 0.5,
        provider_metadata=(("render_job_id", "RJ-20-9"),),
        events=(
            DurableExecutionEvent(
                state=state,
                observed_at=NOW,
                progress=1.0 if state is ProviderExecutionState.COMPLETED else 0.5,
                provider_job_id="prompt-20-9",
            ),
        ),
    )


def _output(
    output_id: str = "PEO-RO-20-9-001", kind: str = "production_video"
) -> ProviderExecutionOutput:
    return ProviderExecutionOutput(
        output_id=output_id,
        relative_path="Xorix/Production/preview/test.mp4",
        media_kind=kind,
        source_output_id=f"RO-{output_id}",
        metadata=(("quality_level", "production"),),
        discovered_at=NOW,
    )


def _service():
    repository = InMemoryGeneratedMediaRepository()
    store = RecordingFileStore()
    service = GeneratedMediaIngestionService(
        GeneratedMediaPersistenceService(repository),
        store,
    )
    return service, repository, store


def test_completed_provider_video_becomes_generated_media_with_full_provenance() -> None:
    service, repository, store = _service()

    result = service.ingest_execution_outputs(_execution(), _task(), (_output(),))[0]

    assert result.created
    assert result.media.kind is GeneratedMediaKind.VIDEO
    assert result.media.state is GeneratedMediaState.GENERATED
    assert result.media.revision == 1
    assert result.media.scope.production_task_id == "PT-20-9-001"
    assert result.media.provenance.execution_id == "PEX-PQ-20-9-PQE-20-9-A001"
    assert result.media.provenance.provider_job_id == "prompt-20-9"
    assert result.media.provenance.render_output_id == "RO-PEO-RO-20-9-001"
    assert result.media.file.checksum_sha256 == "a" * 64
    assert result.media.file.size_bytes == 123
    assert result.media.file.relative_path.startswith(
        "generated_media/XORIX/EP-001/PT-20-9-001/GM-"
    )
    assert repository.get(result.media.media_id) == result.media
    assert len(store.calls) == 1


def test_ingestion_requires_completed_provider_execution() -> None:
    service, _, store = _service()

    with pytest.raises(GeneratedMediaIngestionError, match="COMPLETED"):
        service.ingest_execution_outputs(
            _execution(ProviderExecutionState.RUNNING),
            _task(),
            (_output(),),
        )

    assert store.calls == []


def test_ingestion_rejects_changed_production_authority() -> None:
    service, _, store = _service()

    with pytest.raises(GeneratedMediaIngestionError, match="fingerprint changed"):
        service.ingest_execution_outputs(_execution(), _task("changed-authority"), (_output(),))

    assert store.calls == []


def test_unsupported_provider_media_kind_is_rejected_before_file_copy() -> None:
    service, _, store = _service()

    with pytest.raises(
        GeneratedMediaIngestionError, match="unsupported provider output media kind"
    ):
        service.ingest_execution_outputs(_execution(), _task(), (_output(kind="unknown_blob"),))

    assert store.calls == []


def test_ingestion_is_idempotent_and_does_not_copy_same_output_twice() -> None:
    service, _, store = _service()
    execution = _execution()
    task = _task()
    output = _output()

    first = service.ingest_execution_outputs(execution, task, (output,))[0]
    second = service.ingest_execution_outputs(execution, task, (output,))[0]

    assert first.created
    assert not second.created
    assert first.media == second.media
    assert len(store.calls) == 1


def test_duplicate_provider_output_identities_are_rejected() -> None:
    service, _, store = _service()
    duplicate = _output()

    with pytest.raises(GeneratedMediaIngestionError, match="duplicate output identities"):
        service.ingest_execution_outputs(_execution(), _task(), (duplicate, duplicate))

    assert store.calls == []


def test_multiple_outputs_are_ingested_in_deterministic_output_identity_order() -> None:
    service, _, store = _service()
    output_b = replace(_output("PEO-B"), relative_path="b.mp4")
    output_a = replace(_output("PEO-A"), relative_path="a.mp4")

    results = service.ingest_execution_outputs(_execution(), _task(), (output_b, output_a))

    assert [call[0] for call in store.calls] == ["a.mp4", "b.mp4"]
    assert [result.media.revision for result in results] == [1, 2]
    assert len(results) == 2
