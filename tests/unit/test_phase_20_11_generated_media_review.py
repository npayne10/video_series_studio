from datetime import UTC, datetime

import pytest

from vscs.application.generated_media import (
    GeneratedMediaPersistenceService,
    GeneratedMediaReviewActor,
    GeneratedMediaReviewDecision,
    GeneratedMediaReviewError,
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

NOW = datetime(2026, 8, 19, 14, 0, tzinfo=UTC)


class MemoryRepository:
    def __init__(self, media: GeneratedMedia) -> None:
        self.records = {media.media_id: media}

    def get(self, media_id: str) -> GeneratedMedia | None:
        return self.records.get(media_id)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        self.records[media.media_id] = media
        return media

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(item for item in self.records.values() if item.scope.production_id == production_id)

    def list_for_episode(self, production_id: str, episode_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_production(production_id)
            if item.scope.episode_id == episode_id
        )

    def list_for_scene(
        self, production_id: str, episode_id: str, scene_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_episode(production_id, episode_id)
            if item.scope.scene_id == scene_id
        )

    def list_for_shot(
        self, production_id: str, episode_id: str, scene_id: str, shot_id: str
    ) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.list_for_scene(production_id, episode_id, scene_id)
            if item.scope.shot_id == shot_id
        )

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item
            for item in self.records.values()
            if item.scope.production_task_id == production_task_id
        )

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        return tuple(
            item for item in self.records.values() if item.provenance.execution_id == execution_id
        )


def _media(*, technical_status: str | None = "passed") -> GeneratedMedia:
    metadata = (
        (("technical_validation.status", technical_status),)
        if technical_status is not None
        else ()
    )
    return GeneratedMedia(
        media_id="GM-20-11-001",
        kind=GeneratedMediaKind.VIDEO,
        scope=GeneratedMediaScope(
            production_id="XORIX",
            episode_id="EP-001",
            production_task_id="PT-20-11-001",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        provenance=GeneratedMediaProvenance(
            execution_id="PEX-20-11-001",
            provider_id="LOCAL-COMFYUI-01",
            provider_job_id="prompt-20-11-001",
        ),
        file=GeneratedMediaFile(relative_path="generated_media/XORIX/EP-001/media.mp4"),
        technical_metadata=metadata,
    )


def _actor(actor_id: str) -> GeneratedMediaReviewActor:
    return GeneratedMediaReviewActor(actor_id=actor_id, display_name=actor_id.title())


def _service(media: GeneratedMedia) -> GeneratedMediaReviewService:
    return GeneratedMediaReviewService(
        GeneratedMediaPersistenceService(MemoryRepository(media))
    )


def test_submission_requires_successful_technical_validation() -> None:
    service = _service(_media(technical_status=None))

    with pytest.raises(GeneratedMediaReviewError, match="pass technical validation"):
        service.submit_for_review(
            "GM-20-11-001",
            submitted_by=_actor("submitter-01"),
            reason="Ready for editorial review",
            now=NOW,
        )


def test_submit_for_review_persists_human_audit_identity_and_reason() -> None:
    service = _service(_media())

    submission = service.submit_for_review(
        "GM-20-11-001",
        submitted_by=_actor("submitter-01"),
        reason="Technical checks passed; ready for review",
        now=NOW,
    )

    assert submission.media.state is GeneratedMediaState.UNDER_REVIEW
    event = submission.media.governance_history[-1]
    assert event.actor == "human:submitter-01"
    assert event.reason == "Technical checks passed; ready for review"
    assert event.occurred_at == NOW


def test_approval_requires_under_review_and_nonblank_reason() -> None:
    service = _service(_media())

    with pytest.raises(GeneratedMediaReviewError, match="UNDER_REVIEW"):
        service.approve(
            "GM-20-11-001",
            reviewer=_actor("reviewer-01"),
            reason="Approved",
            now=NOW,
        )

    service.submit_for_review(
        "GM-20-11-001",
        submitted_by=_actor("submitter-01"),
        reason="Ready",
        now=NOW,
    )
    with pytest.raises(GeneratedMediaReviewError, match="cannot be blank"):
        service.approve(
            "GM-20-11-001",
            reviewer=_actor("reviewer-01"),
            reason="   ",
            now=NOW,
        )


def test_human_approval_is_durable_governance_transition() -> None:
    service = _service(_media())
    service.submit_for_review(
        "GM-20-11-001",
        submitted_by=_actor("submitter-01"),
        reason="Ready for final review",
        now=NOW,
    )

    result = service.approve(
        "GM-20-11-001",
        reviewer=_actor("reviewer-01"),
        reason="Continuity and framing accepted",
        now=NOW,
    )

    assert result.decision is GeneratedMediaReviewDecision.APPROVE
    assert result.media.state is GeneratedMediaState.APPROVED
    assert tuple(event.to_state for event in result.media.governance_history) == (
        GeneratedMediaState.UNDER_REVIEW,
        GeneratedMediaState.APPROVED,
    )
    decision_event = result.media.governance_history[-1]
    assert decision_event.actor == "human:reviewer-01"
    assert decision_event.reason == "Continuity and framing accepted"


def test_human_rejection_is_terminal_and_does_not_become_invalid() -> None:
    service = _service(_media())
    service.submit_for_review(
        "GM-20-11-001",
        submitted_by=_actor("submitter-01"),
        reason="Ready for final review",
        now=NOW,
    )

    result = service.reject(
        "GM-20-11-001",
        reviewer=_actor("reviewer-02"),
        reason="Camera motion is not acceptable for the shot",
        now=NOW,
    )

    assert result.decision is GeneratedMediaReviewDecision.REJECT
    assert result.media.state is GeneratedMediaState.REJECTED
    assert result.media.state is not GeneratedMediaState.INVALID
    assert result.media.governance_history[-1].actor == "human:reviewer-02"


def test_approved_or_rejected_media_cannot_receive_another_review_decision() -> None:
    service = _service(_media())
    service.submit_for_review(
        "GM-20-11-001",
        submitted_by=_actor("submitter-01"),
        reason="Ready",
        now=NOW,
    )
    service.approve(
        "GM-20-11-001",
        reviewer=_actor("reviewer-01"),
        reason="Approved",
        now=NOW,
    )

    with pytest.raises(GeneratedMediaReviewError, match="UNDER_REVIEW"):
        service.reject(
            "GM-20-11-001",
            reviewer=_actor("reviewer-02"),
            reason="Second decision",
            now=NOW,
        )
