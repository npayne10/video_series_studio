"""FIFO queue and sequential scheduler for batch prompt compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .batch import (
    BatchCompilationItemResult,
    BatchCompilationJob,
    BatchCompilationProgress,
    BatchCompilationRequest,
    BatchCompilationStatus,
    BatchPromptCompilationService,
)
from .progress import BatchProgressTracker
from .recovery import BatchRecoveryService
from .reporting import BatchReportingService


class BatchQueueStatus(StrEnum):
    """Scheduler-level state for one queued batch."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class BatchQueueEntry:
    """Immutable public snapshot of one scheduled batch."""

    batch_id: str
    request: BatchCompilationRequest
    status: BatchQueueStatus
    enqueued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: BatchCompilationProgress | None = None
    job: BatchCompilationJob | None = None
    cancellation_requested: bool = False


@dataclass(frozen=True, slots=True)
class BatchQueueSnapshot:
    """Immutable snapshot of the complete scheduler queue."""

    entries: tuple[BatchQueueEntry, ...]

    @property
    def pending(self) -> tuple[BatchQueueEntry, ...]:
        return self._with_status(BatchQueueStatus.PENDING)

    @property
    def running(self) -> tuple[BatchQueueEntry, ...]:
        return self._with_status(BatchQueueStatus.RUNNING)

    @property
    def terminal(self) -> tuple[BatchQueueEntry, ...]:
        terminal = {
            BatchQueueStatus.COMPLETED,
            BatchQueueStatus.COMPLETED_WITH_FAILURES,
            BatchQueueStatus.FAILED,
            BatchQueueStatus.CANCELLED,
        }
        return tuple(entry for entry in self.entries if entry.status in terminal)

    def _with_status(self, status: BatchQueueStatus) -> tuple[BatchQueueEntry, ...]:
        return tuple(entry for entry in self.entries if entry.status is status)


@dataclass(slots=True)
class _ScheduledBatch:
    request: BatchCompilationRequest
    enqueued_at: datetime
    status: BatchQueueStatus = BatchQueueStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: BatchCompilationProgress | None = None
    job: BatchCompilationJob | None = None
    cancellation_requested: bool = False

    def snapshot(self) -> BatchQueueEntry:
        return BatchQueueEntry(
            batch_id=self.request.batch_id,
            request=self.request,
            status=self.status,
            enqueued_at=self.enqueued_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            progress=self.progress,
            job=self.job,
            cancellation_requested=self.cancellation_requested,
        )


@dataclass(slots=True)
class BatchCompilationScheduler:
    """Manage FIFO sequential execution of batch compilation requests."""

    compilation_service: BatchPromptCompilationService
    progress_tracker: BatchProgressTracker | None = None
    reporting_service: BatchReportingService | None = None
    recovery_service: BatchRecoveryService | None = None
    _entries: dict[str, _ScheduledBatch] = field(default_factory=dict)
    _order: list[str] = field(default_factory=list)
    _running_batch_id: str | None = None

    def enqueue(self, request: BatchCompilationRequest) -> BatchQueueEntry:
        if request.batch_id in self._entries:
            raise ValueError(f"Batch already scheduled: {request.batch_id}")
        if self.recovery_service is not None:
            self.recovery_service.begin(request)
        scheduled = _ScheduledBatch(request, datetime.now(UTC))
        self._entries[request.batch_id] = scheduled
        self._order.append(request.batch_id)
        return scheduled.snapshot()

    def restore_pending(self, *, retry_failed: bool = True) -> tuple[BatchQueueEntry, ...]:
        """Restore resumable requests not already present in this scheduler."""
        if self.recovery_service is None:
            return ()
        restored: list[BatchQueueEntry] = []
        for checkpoint in self.recovery_service.pending_checkpoints():
            batch_id = checkpoint.request.batch_id
            if batch_id in self._entries:
                continue
            request = self.recovery_service.resumable_request(
                batch_id,
                retry_failed=retry_failed,
            )
            if request is None:
                continue
            scheduled = _ScheduledBatch(request, datetime.now(UTC))
            self._entries[batch_id] = scheduled
            self._order.append(batch_id)
            restored.append(scheduled.snapshot())
        return tuple(restored)

    def get(self, batch_id: str) -> BatchQueueEntry | None:
        entry = self._entries.get(batch_id)
        return entry.snapshot() if entry is not None else None

    def require(self, batch_id: str) -> BatchQueueEntry:
        entry = self.get(batch_id)
        if entry is None:
            raise KeyError(f"Batch not scheduled: {batch_id}")
        return entry

    def snapshot(self) -> BatchQueueSnapshot:
        return BatchQueueSnapshot(
            tuple(self._entries[batch_id].snapshot() for batch_id in self._order)
        )

    def cancel(self, batch_id: str) -> BatchQueueEntry:
        scheduled = self._require_mutable(batch_id)
        if scheduled.status is BatchQueueStatus.PENDING:
            now = datetime.now(UTC)
            scheduled.cancellation_requested = True
            scheduled.status = BatchQueueStatus.CANCELLED
            scheduled.finished_at = now
            return scheduled.snapshot()
        if scheduled.status is BatchQueueStatus.RUNNING:
            scheduled.cancellation_requested = True
            return scheduled.snapshot()
        return scheduled.snapshot()

    def run_next(self) -> BatchQueueEntry | None:
        if self._running_batch_id is not None:
            raise RuntimeError("A batch compilation is already running")
        scheduled = self._next_pending()
        if scheduled is None:
            return None
        scheduled.status = BatchQueueStatus.RUNNING
        scheduled.started_at = datetime.now(UTC)
        self._running_batch_id = scheduled.request.batch_id
        try:
            job = self._compile(scheduled)
            scheduled.job = job
            scheduled.progress = job.progress
            scheduled.status = self._queue_status(job.status)
            scheduled.finished_at = job.finished_at
            if self.progress_tracker is not None:
                self.progress_tracker.update(job.progress, observed_at=job.finished_at)
            if self.reporting_service is not None:
                self.reporting_service.record(job)
        finally:
            self._running_batch_id = None
        return scheduled.snapshot()

    def run_all(self) -> tuple[BatchQueueEntry, ...]:
        completed: list[BatchQueueEntry] = []
        while True:
            entry = self.run_next()
            if entry is None:
                return tuple(completed)
            completed.append(entry)

    def _compile(self, scheduled: _ScheduledBatch) -> BatchCompilationJob:
        def progress_callback(progress: BatchCompilationProgress) -> None:
            self._record_progress(scheduled, progress)

        def cancellation() -> bool:
            return scheduled.cancellation_requested

        if self.recovery_service is None:
            return self.compilation_service.compile(
                scheduled.request,
                on_progress=progress_callback,
                should_cancel=cancellation,
            )

        def record_result(result: BatchCompilationItemResult) -> None:
            assert self.recovery_service is not None
            self.recovery_service.record_result(
                scheduled.request.batch_id,
                result,
            )

        return self.compilation_service.compile(
            scheduled.request,
            on_progress=progress_callback,
            on_result=record_result,
            should_cancel=cancellation,
        )

    def _next_pending(self) -> _ScheduledBatch | None:
        return next(
            (
                self._entries[batch_id]
                for batch_id in self._order
                if self._entries[batch_id].status is BatchQueueStatus.PENDING
            ),
            None,
        )

    def _require_mutable(self, batch_id: str) -> _ScheduledBatch:
        try:
            return self._entries[batch_id]
        except KeyError as exc:
            raise KeyError(f"Batch not scheduled: {batch_id}") from exc

    def _record_progress(
        self,
        scheduled: _ScheduledBatch,
        progress: BatchCompilationProgress,
    ) -> None:
        scheduled.progress = progress
        if self.progress_tracker is not None:
            self.progress_tracker.update(progress)

    @staticmethod
    def _queue_status(status: BatchCompilationStatus) -> BatchQueueStatus:
        return BatchQueueStatus(status.value)
