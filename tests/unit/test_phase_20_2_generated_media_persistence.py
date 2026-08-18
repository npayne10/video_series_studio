"""Focused tests for Phase 20.2 Generated Media persistence."""

from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import (
    GeneratedMediaGovernanceService,
    GeneratedMediaPersistenceService,
    GeneratedMediaRepositoryError,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)
from vscs.infrastructure.generated_media import JsonGeneratedMediaRepository


def _media(
    media_id: str,
    *,
    production_id: str = "PROD-001",
    episode_id: str = "EP-001",
    scene_id: str = "SCN-001",
    shot_id: str = "SHT-001",
    task_id: str = "PT-001",
    execution_id: str = "EXEC-001",
) -> GeneratedMedia:
    return GeneratedMedia(
        media_id=media_id,
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id=production_id,
            episode_id=episode_id,
            scene_id=scene_id,
            shot_id=shot_id,
            production_task_id=task_id,
        ),
        provenance=GeneratedMediaProvenance(
            execution_id=execution_id,
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id=f"JOB-{media_id}",
            render_request_id=f"REQ-{media_id}",
            render_output_id=f"OUT-{media_id}",
            workflow_id="LTX-VIDEO",
            queue_entry_id=f"PQE-{task_id}",
            worker_id="LOCAL-WORKER-01",
            attributes=(("adapter_version", "1.0"),),
        ),
        file=GeneratedMediaFile(
            relative_path=f"generated_media/video/{media_id}.mp4",
            checksum_sha256="a" * 64,
            size_bytes=1024,
        ),
        technical_metadata=(("container", "mp4"),),
        created_at=datetime(2026, 8, 18, 13, 30, tzinfo=UTC),
    )


def test_register_and_reload_survives_repository_restart(tmp_path) -> None:
    root = tmp_path / "project" / "generated_media" / "metadata"
    service = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    original = _media("GM-001")

    service.register(original)

    restarted = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    assert restarted.get("GM-001") == original


def test_register_rejects_duplicate_stable_identity(tmp_path) -> None:
    service = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(tmp_path / "generated_media")
    )
    media = _media("GM-001")
    service.register(media)

    with pytest.raises(GeneratedMediaRepositoryError, match="already exists"):
        service.register(media)


def test_governance_state_and_history_round_trip(tmp_path) -> None:
    root = tmp_path / "generated_media"
    service = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    governance = GeneratedMediaGovernanceService()
    media = service.register(_media("GM-001"))
    media = governance.submit_for_review(media, submitted_by="operator")
    media = governance.approve(
        media,
        reviewed_by="reviewer",
        reason="Accepted for production",
    )
    service.save(media)

    restarted = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    restored = restarted.get("GM-001")

    assert restored is not None
    assert restored.state is GeneratedMediaState.APPROVED
    assert restored.governance_history == media.governance_history
    assert restored == media


def test_scope_task_and_execution_queries_are_deterministic(tmp_path) -> None:
    service = GeneratedMediaPersistenceService(
        JsonGeneratedMediaRepository(tmp_path / "generated_media")
    )
    for media in (
        _media("GM-002"),
        _media("GM-001"),
        _media("GM-003", shot_id="SHT-002", task_id="PT-002", execution_id="EXEC-002"),
        _media(
            "GM-004",
            production_id="PROD-002",
            episode_id="EP-002",
            scene_id="SCN-002",
            shot_id="SHT-003",
            task_id="PT-003",
            execution_id="EXEC-003",
        ),
    ):
        service.register(media)

    assert [item.media_id for item in service.list_for_production("PROD-001")] == [
        "GM-001",
        "GM-002",
        "GM-003",
    ]
    assert [item.media_id for item in service.list_for_episode("PROD-001", "EP-001")] == [
        "GM-001",
        "GM-002",
        "GM-003",
    ]
    assert [
        item.media_id for item in service.list_for_scene("PROD-001", "EP-001", "SCN-001")
    ] == ["GM-001", "GM-002", "GM-003"]
    assert [
        item.media_id
        for item in service.list_for_shot("PROD-001", "EP-001", "SCN-001", "SHT-001")
    ] == ["GM-001", "GM-002"]
    assert [item.media_id for item in service.list_for_task("PT-001")] == ["GM-001", "GM-002"]
    assert [item.media_id for item in service.list_for_execution("EXEC-001")] == [
        "GM-001",
        "GM-002",
    ]


def test_repository_rejects_unsafe_media_identity(tmp_path) -> None:
    repository = JsonGeneratedMediaRepository(tmp_path / "generated_media")

    with pytest.raises(GeneratedMediaRepositoryError, match="filesystem-safe"):
        repository.save(_media("../GM-001"))


def test_repository_rejects_unsupported_schema(tmp_path) -> None:
    root = tmp_path / "generated_media"
    root.mkdir(parents=True)
    (root / "GM-001.json").write_text(
        '{"schema_version":"99.0","generated_media":{}}\n',
        encoding="utf-8",
    )
    repository = JsonGeneratedMediaRepository(root)

    with pytest.raises(GeneratedMediaRepositoryError, match="Unsupported Generated Media"):
        repository.get("GM-001")
