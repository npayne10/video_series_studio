"""Tests for Phase 20.1 authoritative Generated Media domain and governance."""

from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import (
    GeneratedMediaGovernanceError,
    GeneratedMediaGovernanceService,
)
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)


def _media(*, state: GeneratedMediaState = GeneratedMediaState.GENERATED) -> GeneratedMedia:
    return GeneratedMedia(
        media_id="GM-PROD-001-SHT-001-0001",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="PROD-001",
            episode_id="EP-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
            production_task_id="PT-VIDEO-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="EXEC-001",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="PROMPT-001",
            render_request_id="REQ-001",
            render_output_id="OUT-001",
            workflow_id="LTX-VIDEO-PRODUCTION",
            queue_entry_id="PQE-PT-VIDEO-001",
            worker_id="LOCAL-WORKER-01",
        ),
        file=GeneratedMediaFile(
            relative_path="generated_media/video/EP-001/SCN-001/SHT-001/clip.mp4",
            checksum_sha256="a" * 64,
            size_bytes=4096,
        ),
        state=state,
        created_at=datetime(2026, 8, 18, 15, 30, tzinfo=UTC),
    )


def test_generated_media_starts_as_authoritative_generated_record() -> None:
    media = _media()

    assert media.state is GeneratedMediaState.GENERATED
    assert media.scope.production_task_id == "PT-VIDEO-001"
    assert media.provenance.provider_id == "LOCAL-COMFYUI-01"
    assert media.provenance.provider_job_id == "PROMPT-001"
    assert media.file.relative_path == "generated_media/video/EP-001/SCN-001/SHT-001/clip.mp4"
    assert media.file.checksum_sha256 == "a" * 64


def test_generated_media_cannot_be_constructed_as_approved_without_governance_history() -> None:
    with pytest.raises(ValueError, match="must start GENERATED"):
        _media(state=GeneratedMediaState.APPROVED)


def test_human_review_is_required_before_generated_media_approval() -> None:
    governance = GeneratedMediaGovernanceService()
    generated = _media()

    with pytest.raises(GeneratedMediaGovernanceError, match="generated -> approved"):
        governance.approve(
            generated,
            reviewed_by="Neill",
            reason="Approved for production use.",
        )

    under_review = governance.submit_for_review(generated, submitted_by="Neill")
    approved = governance.approve(
        under_review,
        reviewed_by="Neill",
        reason="Approved for production use.",
    )

    assert under_review.state is GeneratedMediaState.UNDER_REVIEW
    assert approved.state is GeneratedMediaState.APPROVED
    assert [event.to_state for event in approved.governance_history] == [
        GeneratedMediaState.UNDER_REVIEW,
        GeneratedMediaState.APPROVED,
    ]
    assert approved.governance_history[-1].actor == "Neill"


def test_rejection_and_invalidation_are_distinct_terminal_governance_outcomes() -> None:
    governance = GeneratedMediaGovernanceService()
    under_review = governance.submit_for_review(_media(), submitted_by="operator")

    rejected = governance.reject(
        under_review,
        reviewed_by="operator",
        reason="Creative continuity does not meet the approved shot intent.",
    )
    invalid = governance.mark_invalid(
        _media(),
        actor="technical-validation",
        reason="Generated file is unreadable.",
    )

    assert rejected.state is GeneratedMediaState.REJECTED
    assert invalid.state is GeneratedMediaState.INVALID
    with pytest.raises(GeneratedMediaGovernanceError, match="rejected -> under_review"):
        governance.submit_for_review(rejected, submitted_by="operator")


def test_only_approved_media_can_be_superseded_with_separate_replacement_identity() -> None:
    governance = GeneratedMediaGovernanceService()
    approved = governance.approve(
        governance.submit_for_review(_media(), submitted_by="operator"),
        reviewed_by="operator",
        reason="Approved master generation.",
    )

    with pytest.raises(GeneratedMediaGovernanceError, match="cannot supersede itself"):
        governance.supersede(
            approved,
            replacement_media_id=approved.media_id,
            actor="operator",
            reason="Replacement selected.",
        )

    superseded = governance.supersede(
        approved,
        replacement_media_id="GM-PROD-001-SHT-001-0002",
        actor="operator",
        reason="A newer approved generation replaces this media.",
    )

    assert superseded.state is GeneratedMediaState.SUPERSEDED
    assert superseded.governance_history[-1].replacement_media_id == "GM-PROD-001-SHT-001-0002"


def test_generated_media_file_identity_rejects_unsafe_paths_and_invalid_checksum() -> None:
    with pytest.raises(ValueError, match="project-relative"):
        GeneratedMediaFile(relative_path="../outside.mp4")

    with pytest.raises(ValueError, match="SHA-256"):
        GeneratedMediaFile(relative_path="generated/video.mp4", checksum_sha256="not-a-checksum")
