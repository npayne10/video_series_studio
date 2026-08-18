"""Provider-neutral runtime queue for approved ProductionTask schedules."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .models import ProductionTaskPriority, ProductionTaskState, ProductionTaskType
from .repository import ProductionTaskRepository
from .schedule_records import (
    ProductionScheduleRepository,
    ProductionScheduleReviewDecision,
    production_schedule_fingerprint,
)


class ProductionQueueError(ValueError):
    """Raised when a ProductionQueue cannot be compiled or transitioned safely."""


class ProductionQueueState(StrEnum):
    """Provider-neutral runtime lifecycle state for one queued ProductionTask."""

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
class ProductionQueueAttempt:
    """One runtime execution attempt for a queued ProductionTask."""

    attempt_number: int
    worker_id: str
    started_at: datetime
    completed_at: datetime | None = None
    succeeded: bool | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.attempt_number < 1:
            raise ValueError("attempt_number must be at least 1")
        _require_text(self.worker_id, "worker_id")


@dataclass(frozen=True, slots=True)
class ProductionQueueEntry:
    """Provider-neutral runtime record for one scheduled ProductionTask."""

    entry_id: str
    task_id: str
    resource_id: str
    task_type: ProductionTaskType
    state: ProductionQueueState
    priority: ProductionTaskPriority
    dependencies: tuple[str, ...] = ()
    maximum_attempts: int = 3
    retry_delay_seconds: int = 0
    attempts: tuple[ProductionQueueAttempt, ...] = ()
    claimed_by: str | None = None
    available_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        _require_text(self.entry_id, "entry_id")
        _require_text(self.task_id, "task_id")
        _require_text(self.resource_id, "resource_id")
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be at least 1")
        if self.retry_delay_seconds < 0:
            raise ValueError("retry_delay_seconds cannot be negative")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies cannot contain duplicates")
        for dependency in self.dependencies:
            _require_text(dependency, "dependency")
        if self.task_id in self.dependencies:
            raise ValueError("a ProductionQueue entry cannot depend on its own task")

    @property
    def attempt_count(self) -> int:
        """Return the number of execution attempts already recorded."""
        return len(self.attempts)


@dataclass(frozen=True, slots=True)
class ProductionQueue:
    """Runtime queue compiled from one approved ProductionSchedule revision."""

    queue_id: str
    production_id: str
    schedule_id: str
    schedule_revision: int
    schedule_fingerprint: str
    entries: tuple[ProductionQueueEntry, ...]
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        _require_text(self.queue_id, "queue_id")
        _require_text(self.production_id, "production_id")
        _require_text(self.schedule_id, "schedule_id")
        _require_text(self.schedule_fingerprint, "schedule_fingerprint")
        _require_text(self.schema_version, "schema_version")
        if self.schedule_revision < 1:
            raise ValueError("schedule_revision must be at least 1")
        entry_ids = tuple(entry.entry_id for entry in self.entries)
        task_ids = tuple(entry.task_id for entry in self.entries)
        if len(set(entry_ids)) != len(entry_ids):
            raise ValueError("ProductionQueue cannot contain duplicate entry identities")
        if len(set(task_ids)) != len(task_ids):
            raise ValueError("ProductionQueue cannot contain duplicate ProductionTasks")

    def entry(self, entry_id: str) -> ProductionQueueEntry | None:
        """Return one queue entry by stable queue-entry identity."""
        return next((entry for entry in self.entries if entry.entry_id == entry_id), None)

    def entry_for_task(self, task_id: str) -> ProductionQueueEntry | None:
        """Return the queue entry representing one ProductionTask."""
        return next((entry for entry in self.entries if entry.task_id == task_id), None)


class ProductionQueueCompilerService:
    """Compile the current approved ProductionSchedule into a general ProductionQueue."""

    def __init__(
        self,
        schedules: ProductionScheduleRepository,
        tasks: ProductionTaskRepository,
    ) -> None:
        self.schedules = schedules
        self.tasks = tasks

    def compile(self, production_id: str, *, now: datetime | None = None) -> ProductionQueue:
        """Compile only the current human-approved schedule revision."""
        normalized = production_id.strip()
        if not normalized:
            raise ProductionQueueError("production_id cannot be blank")
        snapshot = self.schedules.latest_for_production(normalized)
        if snapshot is None:
            raise ProductionQueueError(f"No ProductionSchedule exists for production: {normalized}")
        if production_schedule_fingerprint(snapshot.schedule) != snapshot.fingerprint:
            raise ProductionQueueError(
                "ProductionSchedule fingerprint does not match persisted content"
            )
        reviews = self.schedules.reviews(snapshot.schedule_id, snapshot.revision)
        if len(reviews) != 1:
            raise ProductionQueueError(
                "Current ProductionSchedule must have exactly one review decision"
            )
        review = reviews[0]
        if review.fingerprint != snapshot.fingerprint:
            raise ProductionQueueError("ProductionSchedule review fingerprint is stale")
        if review.decision is not ProductionScheduleReviewDecision.APPROVED:
            raise ProductionQueueError(
                "Current ProductionSchedule is not approved for queue compilation"
            )

        current = now or datetime.now(UTC)
        entries: list[ProductionQueueEntry] = []
        for assignment in snapshot.schedule.assignments:
            task = self.tasks.get(assignment.task_id)
            if task is None:
                raise ProductionQueueError(
                    f"Scheduled ProductionTask not found: {assignment.task_id}"
                )
            if task.production_id != normalized:
                raise ProductionQueueError(
                    f"Scheduled ProductionTask belongs to a different production: {task.task_id}"
                )
            if task.state is not ProductionTaskState.READY:
                raise ProductionQueueError(
                    f"Scheduled ProductionTask is no longer READY: {task.task_id}"
                )
            scheduled_capabilities = tuple(
                sorted(task.capabilities, key=lambda capability: capability.value)
            )
            if (
                assignment.priority is not task.priority
                or assignment.required_capabilities != scheduled_capabilities
            ):
                raise ProductionQueueError(
                    f"Scheduled ProductionTask authority changed after review: {task.task_id}"
                )
            entries.append(
                ProductionQueueEntry(
                    entry_id=f"PQE-{task.task_id}",
                    task_id=task.task_id,
                    resource_id=assignment.resource_id,
                    task_type=task.task_type,
                    state=ProductionQueueState.READY,
                    priority=task.priority,
                    dependencies=task.dependencies,
                    maximum_attempts=task.attempt_policy.maximum_attempts,
                    retry_delay_seconds=task.attempt_policy.retry_delay_seconds,
                    created_at=current,
                    updated_at=current,
                )
            )
        return ProductionQueue(
            queue_id=f"PQ-{snapshot.schedule_id}-R{snapshot.revision:06d}",
            production_id=normalized,
            schedule_id=snapshot.schedule_id,
            schedule_revision=snapshot.revision,
            schedule_fingerprint=snapshot.fingerprint,
            entries=tuple(entries),
        )


class ProductionQueueEngine:
    """Apply provider-neutral runtime transitions to a ProductionQueue."""

    def ready_entries(
        self,
        queue: ProductionQueue,
        now: datetime | None = None,
    ) -> tuple[ProductionQueueEntry, ...]:
        """Return executable entries ordered deterministically by production priority."""
        refreshed = self.refresh(queue, now)
        return tuple(
            sorted(
                (entry for entry in refreshed.entries if entry.state is ProductionQueueState.READY),
                key=lambda item: (-int(item.priority), item.created_at, item.entry_id),
            )
        )

    def refresh(
        self,
        queue: ProductionQueue,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Refresh retry availability without changing active or terminal entries."""
        current = now or datetime.now(UTC)
        refreshed: list[ProductionQueueEntry] = []
        for entry in queue.entries:
            if entry.state is ProductionQueueState.RETRYING and (
                entry.available_at is None or entry.available_at <= current
            ):
                refreshed.append(
                    replace(
                        entry,
                        state=ProductionQueueState.READY,
                        available_at=None,
                        updated_at=current,
                    )
                )
            else:
                refreshed.append(entry)
        return replace(queue, entries=tuple(refreshed))

    def claim(
        self,
        queue: ProductionQueue,
        entry_id: str,
        worker_id: str,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Claim one READY entry for a runtime worker."""
        current = now or datetime.now(UTC)
        refreshed = self.refresh(queue, current)
        entry = self._require_entry(refreshed, entry_id)
        if entry.state is not ProductionQueueState.READY:
            raise ProductionQueueError(f"ProductionQueue entry is not READY: {entry_id}")
        normalized_worker = worker_id.strip()
        if not normalized_worker:
            raise ProductionQueueError("worker_id cannot be blank")
        return self._replace_entry(
            refreshed,
            replace(
                entry,
                state=ProductionQueueState.CLAIMED,
                claimed_by=normalized_worker,
                updated_at=current,
            ),
        )

    def start(
        self,
        queue: ProductionQueue,
        entry_id: str,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Start one claimed entry and record a runtime attempt."""
        current = now or datetime.now(UTC)
        entry = self._require_entry(queue, entry_id)
        if entry.state is not ProductionQueueState.CLAIMED or entry.claimed_by is None:
            raise ProductionQueueError(f"ProductionQueue entry is not CLAIMED: {entry_id}")
        if entry.attempt_count >= entry.maximum_attempts:
            raise ProductionQueueError(f"ProductionQueue entry exhausted attempts: {entry_id}")
        attempt = ProductionQueueAttempt(
            attempt_number=entry.attempt_count + 1,
            worker_id=entry.claimed_by,
            started_at=current,
        )
        return self._replace_entry(
            queue,
            replace(
                entry,
                state=ProductionQueueState.RUNNING,
                attempts=(*entry.attempts, attempt),
                updated_at=current,
            ),
        )

    def complete(
        self,
        queue: ProductionQueue,
        entry_id: str,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Complete one running entry."""
        current = now or datetime.now(UTC)
        entry = self._require_running(queue, entry_id)
        attempts = self._finish_attempt(entry, current, succeeded=True)
        return self._replace_entry(
            queue,
            replace(
                entry,
                state=ProductionQueueState.COMPLETED,
                attempts=attempts,
                claimed_by=None,
                available_at=None,
                updated_at=current,
            ),
        )

    def fail(
        self,
        queue: ProductionQueue,
        entry_id: str,
        error_message: str,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Fail one running entry and schedule retry according to task policy."""
        current = now or datetime.now(UTC)
        entry = self._require_running(queue, entry_id)
        message = error_message.strip()
        if not message:
            raise ProductionQueueError("error_message cannot be blank")
        attempts = self._finish_attempt(entry, current, succeeded=False, error_message=message)
        retryable = len(attempts) < entry.maximum_attempts
        return self._replace_entry(
            queue,
            replace(
                entry,
                state=(ProductionQueueState.RETRYING if retryable else ProductionQueueState.FAILED),
                attempts=attempts,
                claimed_by=None,
                available_at=(
                    current + timedelta(seconds=entry.retry_delay_seconds) if retryable else None
                ),
                updated_at=current,
            ),
        )

    def cancel(
        self,
        queue: ProductionQueue,
        entry_id: str,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Cancel one non-terminal queued task."""
        current = now or datetime.now(UTC)
        entry = self._require_entry(queue, entry_id)
        if entry.state in {
            ProductionQueueState.COMPLETED,
            ProductionQueueState.FAILED,
            ProductionQueueState.CANCELLED,
        }:
            raise ProductionQueueError(f"ProductionQueue entry is already terminal: {entry_id}")
        return self._replace_entry(
            queue,
            replace(
                entry,
                state=ProductionQueueState.CANCELLED,
                claimed_by=None,
                available_at=None,
                updated_at=current,
            ),
        )

    @staticmethod
    def _finish_attempt(
        entry: ProductionQueueEntry,
        completed_at: datetime,
        *,
        succeeded: bool,
        error_message: str | None = None,
    ) -> tuple[ProductionQueueAttempt, ...]:
        if not entry.attempts:
            raise ProductionQueueError(
                f"ProductionQueue entry has no active attempt: {entry.entry_id}"
            )
        latest = entry.attempts[-1]
        if latest.completed_at is not None:
            raise ProductionQueueError(
                f"ProductionQueue entry attempt already completed: {entry.entry_id}"
            )
        finished = replace(
            latest,
            completed_at=completed_at,
            succeeded=succeeded,
            error_message=error_message,
        )
        return (*entry.attempts[:-1], finished)

    @staticmethod
    def _require_entry(queue: ProductionQueue, entry_id: str) -> ProductionQueueEntry:
        entry = queue.entry(entry_id)
        if entry is None:
            raise ProductionQueueError(f"ProductionQueue entry not found: {entry_id}")
        return entry

    @staticmethod
    def _require_running(queue: ProductionQueue, entry_id: str) -> ProductionQueueEntry:
        entry = ProductionQueueEngine._require_entry(queue, entry_id)
        if entry.state is not ProductionQueueState.RUNNING:
            raise ProductionQueueError(f"ProductionQueue entry is not RUNNING: {entry_id}")
        return entry

    @staticmethod
    def _replace_entry(queue: ProductionQueue, updated: ProductionQueueEntry) -> ProductionQueue:
        return replace(
            queue,
            entries=tuple(
                updated if entry.entry_id == updated.entry_id else entry for entry in queue.entries
            ),
        )


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")
