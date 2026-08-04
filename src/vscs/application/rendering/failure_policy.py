"""Declarative renderer failure and retry policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FailureAction(StrEnum):
    """Action selected after a render failure."""

    RETRY = "retry"
    ABORT = "abort"
    CONTINUE = "continue"
    NOTIFY = "notify"
    RESUME = "resume"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Declarative retry and notification behaviour."""

    maximum_retries: int = 2
    retry_delay_seconds: float = 5.0
    retryable_error_codes: frozenset[str] = frozenset()
    abort_error_codes: frozenset[str] = frozenset()
    notify_on_failure: bool = True
    allow_resume: bool = False

    def __post_init__(self) -> None:
        if self.maximum_retries < 0:
            raise ValueError("maximum_retries cannot be negative")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        if self.retryable_error_codes & self.abort_error_codes:
            raise ValueError("An error code cannot be both retryable and abort-only")

    def action_for(self, error_code: str, retry_count: int) -> FailureAction:
        """Return the declared action for one failure."""
        if error_code in self.abort_error_codes:
            return FailureAction.ABORT
        if (
            error_code in self.retryable_error_codes
            and retry_count < self.maximum_retries
        ):
            return FailureAction.RETRY
        return FailureAction.NOTIFY if self.notify_on_failure else FailureAction.ABORT
