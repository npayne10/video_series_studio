"""Live progress tracking and operational metrics for batch compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from .batch import BatchCompilationProgress, BatchCompilationStatus


@dataclass(frozen=True, slots=True)
class BatchProgressMetrics:
    """Calculated timing and throughput metrics for one batch snapshot."""

    elapsed_seconds: float
    estimated_remaining_seconds: float | None
    items_per_minute: float
    success_rate: float


@dataclass(frozen=True, slots=True)
class BatchProgressSnapshot:
    """Immutable live view of one compilation batch."""

    progress: BatchCompilationProgress
    started_at: datetime
    observed_at: datetime
    metrics: BatchProgressMetrics

    @property
    def batch_id(self) -> str:
        return self.progress.batch_id


@dataclass(frozen=True, slots=True)
class BatchProgressEvent:
    """One timestamped progress transition retained by the tracker."""

    snapshot: BatchProgressSnapshot


@dataclass(slots=True)
class BatchProgressTracker:
    """Track immutable progress snapshots for active and completed batches."""

    _started: dict[str, datetime] = field(default_factory=dict)
    _latest: dict[str, BatchProgressSnapshot] = field(default_factory=dict)
    _events: dict[str, list[BatchProgressEvent]] = field(default_factory=dict)

    def update(
        self,
        progress: BatchCompilationProgress,
        *,
        observed_at: datetime | None = None,
    ) -> BatchProgressSnapshot:
        now = observed_at or datetime.now(UTC)
        started = self._started.setdefault(progress.batch_id, now)
        elapsed = max((now - started).total_seconds(), 0.0)
        processed = progress.processed_items
        throughput = processed * 60.0 / elapsed if elapsed > 0.0 else 0.0
        eta = None
        if throughput > 0.0 and progress.remaining_items > 0:
            eta = progress.remaining_items * 60.0 / throughput
        successful = progress.completed_items + progress.skipped_items
        success_rate = successful / processed if processed else 0.0
        snapshot = BatchProgressSnapshot(
            progress=progress,
            started_at=started,
            observed_at=now,
            metrics=BatchProgressMetrics(elapsed, eta, throughput, success_rate),
        )
        self._latest[progress.batch_id] = snapshot
        self._events.setdefault(progress.batch_id, []).append(BatchProgressEvent(snapshot))
        return snapshot

    def latest(self, batch_id: str) -> BatchProgressSnapshot | None:
        return self._latest.get(batch_id)

    def events(self, batch_id: str) -> tuple[BatchProgressEvent, ...]:
        return tuple(self._events.get(batch_id, ()))

    def active(self) -> tuple[BatchProgressSnapshot, ...]:
        terminal = {
            BatchCompilationStatus.COMPLETED,
            BatchCompilationStatus.COMPLETED_WITH_FAILURES,
            BatchCompilationStatus.FAILED,
            BatchCompilationStatus.CANCELLED,
        }
        return tuple(
            self._latest[batch_id]
            for batch_id in sorted(self._latest)
            if self._latest[batch_id].progress.status not in terminal
        )

    @staticmethod
    def eta(snapshot: BatchProgressSnapshot) -> timedelta | None:
        seconds = snapshot.metrics.estimated_remaining_seconds
        return timedelta(seconds=seconds) if seconds is not None else None
