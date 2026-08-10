"""Render job lifecycle contracts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from .outputs import RenderOutput


class RenderJobStatus(StrEnum):
    """Supported render job lifecycle states."""

    QUEUED = "queued"
    PREPARING = "preparing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


_ALLOWED_TRANSITIONS: dict[RenderJobStatus, frozenset[RenderJobStatus]] = {
    RenderJobStatus.QUEUED: frozenset({RenderJobStatus.PREPARING, RenderJobStatus.CANCELLED}),
    RenderJobStatus.PREPARING: frozenset(
        {RenderJobStatus.RUNNING, RenderJobStatus.FAILED, RenderJobStatus.CANCELLED}
    ),
    RenderJobStatus.RUNNING: frozenset(
        {RenderJobStatus.COMPLETED, RenderJobStatus.FAILED, RenderJobStatus.CANCELLED}
    ),
    RenderJobStatus.FAILED: frozenset({RenderJobStatus.RETRYING, RenderJobStatus.CANCELLED}),
    RenderJobStatus.RETRYING: frozenset(
        {RenderJobStatus.PREPARING, RenderJobStatus.FAILED, RenderJobStatus.CANCELLED}
    ),
    RenderJobStatus.COMPLETED: frozenset(),
    RenderJobStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class RenderJob:
    """One renderer execution attempt and its tracked state."""

    job_id: str
    request_id: str
    status: RenderJobStatus = RenderJobStatus.QUEUED
    submitted_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: float = 0.0
    renderer_job_id: str | None = None
    outputs: tuple[RenderOutput, ...] = ()
    failure_reason: str | None = None
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.job_id.strip() or not self.request_id.strip():
            raise ValueError("job_id and request_id are required")
        if not 0.0 <= self.progress <= 1.0:
            raise ValueError("progress must be between 0.0 and 1.0")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")

    def transition(self, status: RenderJobStatus, **changes: object) -> RenderJob:
        """Return a new job after validating its lifecycle transition."""
        if status not in _ALLOWED_TRANSITIONS[self.status]:
            raise ValueError(
                f"Invalid render job transition: {self.status.value} -> {status.value}"
            )
        return replace(self, status=status, **changes)
