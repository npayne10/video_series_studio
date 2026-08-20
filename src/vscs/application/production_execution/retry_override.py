"""Human-governed retry override contracts for Phase 20.16.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class GovernedRetryOverrideState(StrEnum):
    """Operator-facing retry-override availability."""

    NOT_REQUIRED = "not_required"
    ELIGIBLE = "eligible"
    AUTHORIZED = "authorized"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class GovernedRetryAuthorization:
    """One durable human authorization for exactly one additional execution attempt."""

    authorization_id: str
    production_id: str
    task_id: str
    authority_fingerprint: str
    authorized_attempt_number: int
    authorized_by: str
    reason: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        for field_name, value in (
            ("authorization_id", self.authorization_id),
            ("production_id", self.production_id),
            ("task_id", self.task_id),
            ("authority_fingerprint", self.authority_fingerprint),
            ("authorized_by", self.authorized_by),
            ("reason", self.reason),
        ):
            if not value.strip():
                raise ValueError(f"{field_name} cannot be blank")
        if self.authorized_attempt_number < 2:
            raise ValueError("authorized_attempt_number must be at least 2")


@dataclass(frozen=True, slots=True)
class GovernedRetryOverrideStatus:
    """Read-only retry authority status for one ProductionTask."""

    state: GovernedRetryOverrideState
    base_maximum_attempts: int
    attempts_recorded: int
    effective_maximum_attempts: int
    next_attempt_number: int | None = None
    latest_authorization: GovernedRetryAuthorization | None = None
    message: str = ""

    @property
    def eligible(self) -> bool:
        return self.state is GovernedRetryOverrideState.ELIGIBLE

    @property
    def authorized(self) -> bool:
        return self.state is GovernedRetryOverrideState.AUTHORIZED
