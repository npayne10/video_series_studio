"""Explicit human review and approval authority for Generated Media."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from vscs.domain.generated_media import GeneratedMedia, GeneratedMediaState

from .persistence import GeneratedMediaPersistenceService


class GeneratedMediaReviewError(RuntimeError):
    """Raised when Generated Media review authority or lifecycle is invalid."""


class ReviewAuthorityType(StrEnum):
    """Authority kinds accepted by the Generated Media review workflow."""

    HUMAN = "human"


class GeneratedMediaReviewDecision(StrEnum):
    """Explicit terminal human decisions for one review cycle."""

    APPROVE = "approve"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class GeneratedMediaReviewActor:
    """Explicit human identity allowed to submit or decide Generated Media review."""

    actor_id: str
    display_name: str
    authority_type: ReviewAuthorityType = ReviewAuthorityType.HUMAN
    authority_source: str = "vscs-user"

    def __post_init__(self) -> None:
        for field_name, value in (
            ("actor_id", self.actor_id),
            ("display_name", self.display_name),
            ("authority_source", self.authority_source),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.authority_type is not ReviewAuthorityType.HUMAN:
            raise ValueError("Generated Media review authority must be human")

    @property
    def audit_identity(self) -> str:
        return f"human:{self.actor_id.strip()}"


@dataclass(frozen=True, slots=True)
class GeneratedMediaReviewSubmission:
    """Durable review submission represented by Generated Media governance history."""

    media: GeneratedMedia
    submitted_by: GeneratedMediaReviewActor
    reason: str
    submitted_at: datetime


@dataclass(frozen=True, slots=True)
class GeneratedMediaReviewResult:
    """One explicit human review decision and the resulting authoritative media."""

    media: GeneratedMedia
    reviewer: GeneratedMediaReviewActor
    decision: GeneratedMediaReviewDecision
    reason: str
    decided_at: datetime


class GeneratedMediaReviewService:
    """Own explicit human submission, approval, and rejection of Generated Media."""

    TECHNICAL_STATUS_KEY = "technical_validation.status"

    def __init__(self, persistence: GeneratedMediaPersistenceService) -> None:
        self.persistence = persistence

    def submit_for_review(
        self,
        media_id: str,
        *,
        submitted_by: GeneratedMediaReviewActor,
        reason: str,
        now: datetime | None = None,
    ) -> GeneratedMediaReviewSubmission:
        """Submit technically valid GENERATED media for explicit human review."""
        current = now or datetime.now(UTC)
        media = self._require_media(media_id)
        self._require_human(submitted_by)
        message = self._require_reason(reason)
        if media.state is not GeneratedMediaState.GENERATED:
            raise GeneratedMediaReviewError(
                "Generated Media must be GENERATED before review submission"
            )
        if self._technical_status(media) != "passed":
            raise GeneratedMediaReviewError(
                "Generated Media must pass technical validation before human review"
            )
        updated = self.persistence.governance.submit_for_review(
            media,
            submitted_by=submitted_by.audit_identity,
            reason=message,
            occurred_at=current,
        )
        saved = self.persistence.save(updated)
        return GeneratedMediaReviewSubmission(
            media=saved,
            submitted_by=submitted_by,
            reason=message,
            submitted_at=current,
        )

    def decide(
        self,
        media_id: str,
        *,
        reviewer: GeneratedMediaReviewActor,
        decision: GeneratedMediaReviewDecision,
        reason: str,
        now: datetime | None = None,
    ) -> GeneratedMediaReviewResult:
        """Apply one explicit human APPROVE or REJECT decision to UNDER_REVIEW media."""
        current = now or datetime.now(UTC)
        media = self._require_media(media_id)
        self._require_human(reviewer)
        message = self._require_reason(reason)
        if media.state is not GeneratedMediaState.UNDER_REVIEW:
            raise GeneratedMediaReviewError(
                "Generated Media must be UNDER_REVIEW before a review decision"
            )
        if self._technical_status(media) != "passed":
            raise GeneratedMediaReviewError(
                "Generated Media technical validation must remain passed during review"
            )
        if decision is GeneratedMediaReviewDecision.APPROVE:
            updated = self.persistence.governance.approve(
                media,
                reviewed_by=reviewer.audit_identity,
                reason=message,
                occurred_at=current,
            )
        elif decision is GeneratedMediaReviewDecision.REJECT:
            updated = self.persistence.governance.reject(
                media,
                reviewed_by=reviewer.audit_identity,
                reason=message,
                occurred_at=current,
            )
        else:  # pragma: no cover - defensive for future enum extension
            raise GeneratedMediaReviewError(f"Unsupported review decision: {decision}")
        saved = self.persistence.save(updated)
        return GeneratedMediaReviewResult(
            media=saved,
            reviewer=reviewer,
            decision=decision,
            reason=message,
            decided_at=current,
        )

    def approve(
        self,
        media_id: str,
        *,
        reviewer: GeneratedMediaReviewActor,
        reason: str,
        now: datetime | None = None,
    ) -> GeneratedMediaReviewResult:
        return self.decide(
            media_id,
            reviewer=reviewer,
            decision=GeneratedMediaReviewDecision.APPROVE,
            reason=reason,
            now=now,
        )

    def reject(
        self,
        media_id: str,
        *,
        reviewer: GeneratedMediaReviewActor,
        reason: str,
        now: datetime | None = None,
    ) -> GeneratedMediaReviewResult:
        return self.decide(
            media_id,
            reviewer=reviewer,
            decision=GeneratedMediaReviewDecision.REJECT,
            reason=reason,
            now=now,
        )

    def _require_media(self, media_id: str) -> GeneratedMedia:
        normalized = media_id.strip()
        if not normalized:
            raise GeneratedMediaReviewError("media_id cannot be blank")
        media = self.persistence.get(normalized)
        if media is None:
            raise GeneratedMediaReviewError(f"Generated Media not found: {normalized}")
        return media

    @staticmethod
    def _require_human(actor: GeneratedMediaReviewActor) -> None:
        if actor.authority_type is not ReviewAuthorityType.HUMAN:
            raise GeneratedMediaReviewError("Generated Media review requires human authority")

    @staticmethod
    def _require_reason(reason: str) -> str:
        normalized = reason.strip()
        if not normalized:
            raise GeneratedMediaReviewError("review reason/comment cannot be blank")
        return normalized

    @classmethod
    def _technical_status(cls, media: GeneratedMedia) -> str | None:
        values = dict(media.technical_metadata)
        raw = values.get(cls.TECHNICAL_STATUS_KEY)
        return raw.strip().casefold() if raw is not None else None
