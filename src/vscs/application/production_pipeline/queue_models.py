"""Runtime models for dependency-aware production render queues."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum


class QueuePriority(IntEnum):
    """Scheduling priority for one queue entry."""

    LOW = 10
    NORMAL = 20
    HIGH = 30
    URGENT = 40


class QueueState(StrEnum):
    """Runtime lifecycle state for one queue entry."""

    WAITING = "waiting"
    READY = "ready"
    CLAIMED = "claimed"
    RUNNING = "running"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class QueueAttempt:
    """One execution attempt for a queue entry."""

    attempt_number: int
    worker_id: str
    started_at: datetime
    completed_at: datetime | None = None
    succeeded: bool | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RenderQueueEntry:
    """Runtime scheduling record for one renderer-neutral render job."""

    entry_id: str
    job_id: str
    clip_id: str
    state: QueueState = QueueState.WAITING
    priority: QueuePriority = QueuePriority.NORMAL
    dependencies: tuple[str, ...] = ()
    maximum_attempts: int = 3
    attempts: tuple[QueueAttempt, ...] = ()
    claimed_by: str | None = None
    available_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: tuple[tuple[str, str], ...] = ()

    @property
    def attempt_count(self) -> int:
        """Return the number of attempts already recorded."""
        return len(self.attempts)


@dataclass(frozen=True, slots=True)
class RenderQueue:
    """Versioned runtime queue for one production pipeline."""

    queue_id: str
    pipeline_id: str
    entries: tuple[RenderQueueEntry, ...]
    schema_version: str = "1.0"
    metadata: dict[str, str] = field(default_factory=dict)

    def entry(self, entry_id: str) -> RenderQueueEntry | None:
        """Return one queue entry by identity."""
        return next((entry for entry in self.entries if entry.entry_id == entry_id), None)
