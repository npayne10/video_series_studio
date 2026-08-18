from datetime import UTC, datetime
from hashlib import sha256

from vscs.application.generated_media import (
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
from vscs.domain.generated_media import GeneratedMediaKind, GeneratedMediaState
from vscs.infrastructure.generated_media import (
    JsonGeneratedMediaRepository,
    LocalGeneratedMediaFileStore,
)

NOW = datetime(2026, 8, 18, 21, 15, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-20-9-LIVE-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-20-9-LIVE-001",
            revision=1,
            fingerprint="authority-20-9-live",
            approved=True,
            approved_by="reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("production_video",),
        state=ProductionTaskState.READY,
    )


def _execution() -> DurableExecutionJob:
    return DurableExecutionJob(
        execution_id="PEX-PQ-20-9-LIVE-PQE-20-9-LIVE-A001",
        production_id="XORIX",
        task_id="PT-20-9-LIVE-001",
        queue_id="PQ-20-9-LIVE",
        entry_id="PQE-20-9-LIVE",
        resource_id="LOCAL-GPU-01",
        worker_id="WORKER-01",
        lease_id="PLEASE-20-9-LIVE",
        attempt_number=1,
        authority_fingerprint="authority-20-9-live",
        provider_id="LOCAL-COMFYUI-01",
        provider_job_id="prompt-20-9-live",
        render_request_id="REQ-20-9-LIVE",
        workflow_id="video_production_engine_v7_1_4",
        state=ProviderExecutionState.COMPLETED,
        created_at=NOW,
        updated_at=NOW,
        submitted_at=NOW,
        progress=1.0,
        provider_metadata=(
            ("render_job_id", "RJ-20-9-LIVE"),
            ("request_id", "REQ-20-9-LIVE"),
        ),
        events=(
            DurableExecutionEvent(
                state=ProviderExecutionState.COMPLETED,
                observed_at=NOW,
                progress=1.0,
                provider_job_id="prompt-20-9-live",
            ),
        ),
    )


def test_completed_provider_output_is_copied_persisted_and_restart_idempotent(tmp_path) -> None:
    source_root = tmp_path / "provider-output"
    project_root = tmp_path / "project"
    source_file = source_root / "Xorix" / "Production" / "preview" / "clip.mp4"
    source_file.parent.mkdir(parents=True)
    payload = b"phase-20-9-generated-media-content\x00\x01"
    source_file.write_bytes(payload)

    repository_root = project_root / ".vscs" / "generated_media_records"
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(repository_root))
    service = GeneratedMediaIngestionService(
        persistence,
        LocalGeneratedMediaFileStore(source_root, project_root),
    )
    output = ProviderExecutionOutput(
        output_id="PEO-RO-20-9-LIVE-001",
        relative_path="Xorix/Production/preview/clip.mp4",
        media_kind="production_video",
        source_output_id="RO-20-9-LIVE-001",
        metadata=(
            ("renderer", "comfyui"),
            ("quality_level", "production"),
        ),
        discovered_at=NOW,
    )

    created = service.ingest_execution_outputs(_execution(), _task(), (output,))[0]

    assert created.created
    media = created.media
    assert media.kind is GeneratedMediaKind.VIDEO
    assert media.state is GeneratedMediaState.GENERATED
    assert media.scope.production_id == "XORIX"
    assert media.scope.production_task_id == "PT-20-9-LIVE-001"
    assert media.provenance.provider_id == "LOCAL-COMFYUI-01"
    assert media.provenance.provider_job_id == "prompt-20-9-live"
    assert media.provenance.render_output_id == "RO-20-9-LIVE-001"
    assert media.file.checksum_sha256 == sha256(payload).hexdigest()
    assert media.file.size_bytes == len(payload)
    managed_path = project_root / media.file.relative_path
    assert managed_path.read_bytes() == payload
    assert source_file.read_bytes() == payload

    restarted_persistence = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(repository_root)
    )
    restarted_service = GeneratedMediaIngestionService(
        restarted_persistence,
        LocalGeneratedMediaFileStore(source_root, project_root),
    )
    restored = restarted_persistence.list_for_execution(_execution().execution_id)

    assert restored == (media,)
    repeated = restarted_service.ingest_execution_outputs(_execution(), _task(), (output,))[0]
    assert not repeated.created
    assert repeated.media == media
    assert managed_path.read_bytes() == payload
