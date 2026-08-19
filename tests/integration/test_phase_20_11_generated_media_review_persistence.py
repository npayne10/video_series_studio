from datetime import UTC, datetime, timedelta

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaReviewActor,
    GeneratedMediaReviewService,
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

NOW = datetime(2026, 8, 19, 14, 30, tzinfo=UTC)


def _media() -> GeneratedMedia:
    return GeneratedMedia(
        media_id="GM-20-11-INTEGRATION-001",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-11-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="PEX-20-11-INTEGRATION-001",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="prompt-20-11-integration-001",
            render_request_id="REQ-20-11-001",
            render_output_id="RO-20-11-001",
            workflow_id="video_production_engine_v7_1_4",
            queue_entry_id="PQE-20-11-001",
            worker_id="WORKER-01",
        ),
        file=GeneratedMediaFile(
            relative_path="generated_media/XORIX/EP-001/PT-20-11-001/media.mp4",
            checksum_sha256="a" * 64,
            size_bytes=4096,
        ),
        technical_metadata=(
            ("technical_validation.status", "passed"),
            ("technical_validation.validator", "vscs:technical-validator"),
        ),
    )


def _actor(actor_id: str, display_name: str) -> GeneratedMediaReviewActor:
    return GeneratedMediaReviewActor(actor_id=actor_id, display_name=display_name)


def test_review_submission_and_approval_survive_repository_restart(tmp_path) -> None:
    root = tmp_path / "generated_media_records"
    persistence = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    persistence.register(_media())
    review = GeneratedMediaReviewService(persistence)

    submission = review.submit_for_review(
        "GM-20-11-INTEGRATION-001",
        submitted_by=_actor("producer-01", "Producer One"),
        reason="Technical validation passed; submit for human review",
        now=NOW,
    )
    assert submission.media.state is GeneratedMediaState.UNDER_REVIEW

    after_submission_restart = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    restored_under_review = after_submission_restart.get("GM-20-11-INTEGRATION-001")
    assert restored_under_review is not None
    assert restored_under_review.state is GeneratedMediaState.UNDER_REVIEW
    assert restored_under_review.governance_history[-1].actor == "human:producer-01"

    restarted_review = GeneratedMediaReviewService(after_submission_restart)
    approved = restarted_review.approve(
        "GM-20-11-INTEGRATION-001",
        reviewer=_actor("reviewer-01", "Reviewer One"),
        reason="Human review accepted visual continuity and production intent",
        now=NOW + timedelta(minutes=5),
    )
    assert approved.media.state is GeneratedMediaState.APPROVED

    after_approval_restart = GeneratedMediaPersistenceService(JsonGeneratedMediaRepository(root))
    restored_approved = after_approval_restart.get("GM-20-11-INTEGRATION-001")
    assert restored_approved is not None
    assert restored_approved.state is GeneratedMediaState.APPROVED
    assert tuple(event.actor for event in restored_approved.governance_history) == (
        "human:producer-01",
        "human:reviewer-01",
    )
    assert tuple(event.reason for event in restored_approved.governance_history) == (
        "Technical validation passed; submit for human review",
        "Human review accepted visual continuity and production intent",
    )
