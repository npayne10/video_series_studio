"""Integration acceptance for Phase 20.2 Generated Media restart persistence."""

from datetime import UTC, datetime

from vscs.application.generated_media import (
    GeneratedMediaGovernanceService,
    GeneratedMediaPersistenceService,
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


def test_generated_media_authority_survives_restart_with_governance_history(tmp_path) -> None:
    root = tmp_path / "project" / "generated_media" / "metadata"
    service = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    governance = GeneratedMediaGovernanceService()
    media = GeneratedMedia(
        media_id="GM-ACCEPT-001",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="PROD-ACCEPT",
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            production_task_id="PT-ACCEPT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="EXEC-ACCEPT-001",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="COMFY-JOB-001",
            render_request_id="REQ-001",
            render_output_id="OUT-001",
            workflow_id="LTX-VIDEO",
            queue_entry_id="PQE-PT-ACCEPT-001",
            worker_id="LOCAL-WORKER-01",
        ),
        file=GeneratedMediaFile(
            relative_path="generated_media/video/PROD-ACCEPT/SHT-001/GM-ACCEPT-001.mp4",
            checksum_sha256="b" * 64,
            size_bytes=4096,
        ),
        technical_metadata=(("container", "mp4"), ("quality", "production")),
        created_at=datetime(2026, 8, 18, 13, 45, tzinfo=UTC),
    )
    service.register(media)
    reviewed = governance.submit_for_review(media, submitted_by="operator")
    approved = governance.approve(
        reviewed,
        reviewed_by="reviewer",
        reason="Functional acceptance output approved",
    )
    service.save(approved)

    restarted = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    restored = restarted.get("GM-ACCEPT-001")

    assert restored == approved
    assert restored is not None
    assert restored.state is GeneratedMediaState.APPROVED
    assert len(restored.governance_history) == 2
    assert restarted.list_for_task("PT-ACCEPT-001") == (approved,)
    assert restarted.list_for_execution("EXEC-ACCEPT-001") == (approved,)
