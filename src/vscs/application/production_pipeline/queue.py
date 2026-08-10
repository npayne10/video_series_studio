"""Dependency-aware render queue state transitions and scheduling."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from .queue_models import (
    QueueAttempt,
    QueuePriority,
    QueueState,
    RenderQueue,
    RenderQueueEntry,
)


class RenderQueueError(ValueError):
    """Raised when an invalid queue transition is requested."""


class RenderQueueEngine:
    """Apply deterministic scheduling and lifecycle transitions to a render queue."""

    def refresh(self, queue: RenderQueue, now: datetime | None = None) -> RenderQueue:
        """Recalculate waiting, ready, retrying, and blocked states."""
        current = now or datetime.now(UTC)
        states = {entry.entry_id: entry.state for entry in queue.entries}
        refreshed: list[RenderQueueEntry] = []
        for entry in queue.entries:
            if entry.state in {
                QueueState.CLAIMED,
                QueueState.RUNNING,
                QueueState.COMPLETED,
                QueueState.FAILED,
                QueueState.CANCELLED,
            }:
                refreshed.append(entry)
                continue
            dependency_states = tuple(states.get(value) for value in entry.dependencies)
            if any(
                state in {QueueState.FAILED, QueueState.CANCELLED, QueueState.BLOCKED}
                for state in dependency_states
            ):
                state = QueueState.BLOCKED
            elif not all(state is QueueState.COMPLETED for state in dependency_states):
                state = QueueState.WAITING
            elif entry.available_at is not None and entry.available_at > current:
                state = QueueState.RETRYING
            else:
                state = QueueState.READY
            refreshed.append(replace(entry, state=state, updated_at=current))
        return replace(queue, entries=tuple(refreshed))

    def ready_entries(
        self,
        queue: RenderQueue,
        now: datetime | None = None,
    ) -> tuple[RenderQueueEntry, ...]:
        """Return ready entries ordered by priority and creation time."""
        refreshed = self.refresh(queue, now)
        ready = (entry for entry in refreshed.entries if entry.state is QueueState.READY)
        return tuple(
            sorted(
                ready,
                key=lambda item: (-int(item.priority), item.created_at, item.entry_id),
            )
        )

    def claim(
        self,
        queue: RenderQueue,
        entry_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> RenderQueue:
        """Claim one ready entry for a worker."""
        current = now or datetime.now(UTC)
        refreshed = self.refresh(queue, current)
        entry = self._require_entry(refreshed, entry_id)
        if entry.state is not QueueState.READY:
            raise RenderQueueError(f"Queue entry is not ready: {entry_id}")
        if not worker_id.strip():
            raise RenderQueueError("worker_id must not be empty")
        updated = replace(
            entry,
            state=QueueState.CLAIMED,
            claimed_by=worker_id.strip(),
            updated_at=current,
        )
        return self._replace_entry(refreshed, updated)

    def start(
        self,
        queue: RenderQueue,
        entry_id: str,
        now: datetime | None = None,
    ) -> RenderQueue:
        """Start a claimed entry and append a new attempt."""
        current = now or datetime.now(UTC)
        entry = self._require_entry(queue, entry_id)
        if entry.state is not QueueState.CLAIMED or entry.claimed_by is None:
            raise RenderQueueError(f"Queue entry is not claimed: {entry_id}")
        if entry.attempt_count >= entry.maximum_attempts:
            raise RenderQueueError(f"Queue entry has exhausted its attempts: {entry_id}")
        attempt = QueueAttempt(
            attempt_number=entry.attempt_count + 1,
            worker_id=entry.claimed_by,
            started_at=current,
        )
        updated = replace(
            entry,
            state=QueueState.RUNNING,
            attempts=(*entry.attempts, attempt),
            updated_at=current,
        )
        return self._replace_entry(queue, updated)

    def complete(
        self,
        queue: RenderQueue,
        entry_id: str,
        now: datetime | None = None,
    ) -> RenderQueue:
        """Mark a running entry completed."""
        current = now or datetime.now(UTC)
        entry = self._require_running(queue, entry_id)
        attempts = self._finish_latest_attempt(entry, current, succeeded=True)
        updated = replace(
            entry,
            state=QueueState.COMPLETED,
            attempts=attempts,
            claimed_by=None,
            available_at=None,
            updated_at=current,
        )
        return self.refresh(self._replace_entry(queue, updated), current)

    def fail(
        self,
        queue: RenderQueue,
        entry_id: str,
        error_message: str,
        *,
        retry_delay_seconds: float = 0.0,
        now: datetime | None = None,
    ) -> RenderQueue:
        """Fail a running entry and schedule retry when attempts remain."""
        current = now or datetime.now(UTC)
        entry = self._require_running(queue, entry_id)
        attempts = self._finish_latest_attempt(
            entry,
            current,
            succeeded=False,
            error_message=error_message,
        )
        retryable = len(attempts) < entry.maximum_attempts
        state = QueueState.RETRYING if retryable else QueueState.FAILED
        available_at = current + timedelta(seconds=retry_delay_seconds) if retryable else None
        updated = replace(
            entry,
            state=state,
            attempts=attempts,
            claimed_by=None,
            available_at=available_at,
            updated_at=current,
        )
        return self.refresh(self._replace_entry(queue, updated), current)

    def cancel(
        self,
        queue: RenderQueue,
        entry_id: str,
        now: datetime | None = None,
    ) -> RenderQueue:
        """Cancel a non-terminal queue entry."""
        current = now or datetime.now(UTC)
        entry = self._require_entry(queue, entry_id)
        if entry.state in {QueueState.COMPLETED, QueueState.FAILED, QueueState.CANCELLED}:
            raise RenderQueueError(f"Queue entry is already terminal: {entry_id}")
        updated = replace(
            entry,
            state=QueueState.CANCELLED,
            claimed_by=None,
            available_at=None,
            updated_at=current,
        )
        return self.refresh(self._replace_entry(queue, updated), current)

    def reprioritize(
        self,
        queue: RenderQueue,
        entry_id: str,
        priority: QueuePriority,
        now: datetime | None = None,
    ) -> RenderQueue:
        """Change one queue entry priority."""
        current = now or datetime.now(UTC)
        entry = self._require_entry(queue, entry_id)
        updated = replace(entry, priority=priority, updated_at=current)
        return self._replace_entry(queue, updated)

    @staticmethod
    def _finish_latest_attempt(
        entry: RenderQueueEntry,
        completed_at: datetime,
        *,
        succeeded: bool,
        error_message: str | None = None,
    ) -> tuple[QueueAttempt, ...]:
        if not entry.attempts:
            raise RenderQueueError(f"Queue entry has no active attempt: {entry.entry_id}")
        latest = entry.attempts[-1]
        if latest.completed_at is not None:
            raise RenderQueueError(f"Queue entry attempt is already complete: {entry.entry_id}")
        finished = replace(
            latest,
            completed_at=completed_at,
            succeeded=succeeded,
            error_message=error_message,
        )
        return (*entry.attempts[:-1], finished)

    @staticmethod
    def _require_running(queue: RenderQueue, entry_id: str) -> RenderQueueEntry:
        entry = RenderQueueEngine._require_entry(queue, entry_id)
        if entry.state is not QueueState.RUNNING:
            raise RenderQueueError(f"Queue entry is not running: {entry_id}")
        return entry

    @staticmethod
    def _require_entry(queue: RenderQueue, entry_id: str) -> RenderQueueEntry:
        entry = queue.entry(entry_id)
        if entry is None:
            raise RenderQueueError(f"Queue entry not found: {entry_id}")
        return entry

    @staticmethod
    def _replace_entry(queue: RenderQueue, updated: RenderQueueEntry) -> RenderQueue:
        return replace(
            queue,
            entries=tuple(
                updated if entry.entry_id == updated.entry_id else entry for entry in queue.entries
            ),
        )
