"""Governance policy and transitions for authoritative Generated Media."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar

from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaGovernanceEvent,
    GeneratedMediaState,
)


class GeneratedMediaGovernanceSeverity(StrEnum):
    """Severity of one Generated Media governance finding."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class GeneratedMediaGovernanceIssue:
    """One deterministic Generated Media governance finding."""

    code: str
    message: str
    severity: GeneratedMediaGovernanceSeverity = GeneratedMediaGovernanceSeverity.ERROR


@dataclass(frozen=True, slots=True)
class GeneratedMediaGovernanceResult:
    """Deterministic validation result for one Generated Media record."""

    media_id: str
    issues: tuple[GeneratedMediaGovernanceIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(
            issue.severity is GeneratedMediaGovernanceSeverity.ERROR for issue in self.issues
        )


class GeneratedMediaGovernanceError(ValueError):
    """Raised when Generated Media violates governance or transition rules."""


class GeneratedMediaGovernanceService:
    """Own explicit human-governed transitions for authoritative Generated Media."""

    _ALLOWED_TRANSITIONS: ClassVar[dict[GeneratedMediaState, frozenset[GeneratedMediaState]]] = {
        GeneratedMediaState.GENERATED: frozenset(
            {GeneratedMediaState.UNDER_REVIEW, GeneratedMediaState.INVALID}
        ),
        GeneratedMediaState.UNDER_REVIEW: frozenset(
            {
                GeneratedMediaState.APPROVED,
                GeneratedMediaState.REJECTED,
                GeneratedMediaState.INVALID,
            }
        ),
        GeneratedMediaState.APPROVED: frozenset(
            {GeneratedMediaState.SUPERSEDED, GeneratedMediaState.INVALID}
        ),
        GeneratedMediaState.REJECTED: frozenset(),
        GeneratedMediaState.INVALID: frozenset(),
        GeneratedMediaState.SUPERSEDED: frozenset(),
    }

    def validate(self, media: GeneratedMedia) -> GeneratedMediaGovernanceResult:
        """Validate domain authority and governance history without mutation."""
        issues: list[GeneratedMediaGovernanceIssue] = []

        if media.scope.production_task_id.strip() == "":
            issues.append(
                GeneratedMediaGovernanceIssue(
                    code="missing-production-task",
                    message="Generated Media must be owned by an authoritative ProductionTask.",
                )
            )
        if media.provenance.execution_id.strip() == "":
            issues.append(
                GeneratedMediaGovernanceIssue(
                    code="missing-execution-provenance",
                    message="Generated Media must retain provider execution provenance.",
                )
            )

        expected_state = GeneratedMediaState.GENERATED
        for event in media.governance_history:
            if event.from_state is not expected_state:
                issues.append(
                    GeneratedMediaGovernanceIssue(
                        code="discontinuous-governance-history",
                        message="Generated Media governance history is not continuous.",
                    )
                )
                break
            if event.to_state not in self._ALLOWED_TRANSITIONS[event.from_state]:
                issues.append(
                    GeneratedMediaGovernanceIssue(
                        code="invalid-governance-transition",
                        message=(
                            "Generated Media governance transition is not allowed: "
                            f"{event.from_state.value} -> {event.to_state.value}."
                        ),
                    )
                )
            expected_state = event.to_state

        if expected_state is not media.state:
            issues.append(
                GeneratedMediaGovernanceIssue(
                    code="governance-state-mismatch",
                    message="Generated Media state does not match its governance history.",
                )
            )

        return GeneratedMediaGovernanceResult(media_id=media.media_id, issues=tuple(issues))

    def require_valid(self, media: GeneratedMedia) -> None:
        """Raise when a Generated Media record violates blocking governance rules."""
        result = self.validate(media)
        if result.valid:
            return
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in result.issues)
        raise GeneratedMediaGovernanceError(
            f"Generated Media {media.media_id!r} failed governance: {details}"
        )

    def submit_for_review(
        self,
        media: GeneratedMedia,
        *,
        submitted_by: str,
        reason: str = "Submitted for human review",
        occurred_at: datetime | None = None,
    ) -> GeneratedMedia:
        return self._transition(
            media,
            GeneratedMediaState.UNDER_REVIEW,
            actor=submitted_by,
            reason=reason,
            occurred_at=occurred_at,
        )

    def approve(
        self,
        media: GeneratedMedia,
        *,
        reviewed_by: str,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> GeneratedMedia:
        """Approve media only through explicit human review authority."""
        return self._transition(
            media,
            GeneratedMediaState.APPROVED,
            actor=reviewed_by,
            reason=reason,
            occurred_at=occurred_at,
        )

    def reject(
        self,
        media: GeneratedMedia,
        *,
        reviewed_by: str,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> GeneratedMedia:
        """Reject media only through explicit human review authority."""
        return self._transition(
            media,
            GeneratedMediaState.REJECTED,
            actor=reviewed_by,
            reason=reason,
            occurred_at=occurred_at,
        )

    def mark_invalid(
        self,
        media: GeneratedMedia,
        *,
        actor: str,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> GeneratedMedia:
        """Invalidate unusable media without treating technical failure as human rejection."""
        return self._transition(
            media,
            GeneratedMediaState.INVALID,
            actor=actor,
            reason=reason,
            occurred_at=occurred_at,
        )

    def supersede(
        self,
        media: GeneratedMedia,
        *,
        replacement_media_id: str,
        actor: str,
        reason: str,
        occurred_at: datetime | None = None,
    ) -> GeneratedMedia:
        """Retire approved media in favour of a separately identified replacement."""
        if replacement_media_id.strip() == media.media_id:
            raise GeneratedMediaGovernanceError("Generated Media cannot supersede itself")
        return self._transition(
            media,
            GeneratedMediaState.SUPERSEDED,
            actor=actor,
            reason=reason,
            replacement_media_id=replacement_media_id,
            occurred_at=occurred_at,
        )

    def _transition(
        self,
        media: GeneratedMedia,
        target: GeneratedMediaState,
        *,
        actor: str,
        reason: str,
        replacement_media_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> GeneratedMedia:
        self.require_valid(media)
        if target not in self._ALLOWED_TRANSITIONS[media.state]:
            raise GeneratedMediaGovernanceError(
                f"Generated Media transition is not allowed: {media.state.value} -> {target.value}"
            )
        event = GeneratedMediaGovernanceEvent(
            from_state=media.state,
            to_state=target,
            actor=actor,
            reason=reason,
            occurred_at=occurred_at or datetime.now(UTC),
            replacement_media_id=replacement_media_id,
        )
        updated = replace(
            media,
            state=target,
            governance_history=(*media.governance_history, event),
        )
        self.require_valid(updated)
        return updated
