"""Production monitoring snapshots, metrics, and stalled-work diagnostics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .executors import ExecutionLease, ExecutionResult, WorkerIdentity
from .models import ProductionPipeline, ProductionState
from .queue_models import QueueState, RenderQueue


class WorkerHealth(StrEnum):
    """Observed health state for one production worker."""

    HEALTHY = "healthy"
    STALE = "stale"
    OFFLINE = "offline"


class MonitoringSeverity(StrEnum):
    """Severity for one monitoring diagnostic."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WorkerObservation:
    """Latest monitoring data for one worker."""

    worker: WorkerIdentity
    last_heartbeat_at: datetime
    active_lease: ExecutionLease | None = None


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    """Dashboard-ready worker health snapshot."""

    worker_id: str
    executor_id: str
    health: WorkerHealth
    available: bool
    last_heartbeat_at: datetime
    active_job_id: str | None
    lease_expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class QueueProgressSnapshot:
    """Aggregated render queue state counts."""

    total: int
    waiting: int
    ready: int
    claimed: int
    running: int
    retrying: int
    completed: int
    failed: int
    cancelled: int
    blocked: int
    completion_percentage: float


@dataclass(frozen=True, slots=True)
class PipelineProgressSnapshot:
    """Aggregated production pipeline state counts."""

    total: int
    pending: int
    ready: int
    blocked: int
    running: int
    completed: int
    failed: int
    cancelled: int
    completion_percentage: float


@dataclass(frozen=True, slots=True)
class ExecutionMetrics:
    """Duration and failure metrics derived from execution results."""

    total_results: int
    succeeded: int
    failed: int
    success_percentage: float
    average_duration_seconds: float
    maximum_duration_seconds: float
    failures_by_code: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class ProductionEvent:
    """Immutable monitoring event suitable for logs or dashboards."""

    event_id: str
    event_type: str
    occurred_at: datetime
    message: str
    worker_id: str | None = None
    job_id: str | None = None
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class MonitoringDiagnostic:
    """One stalled or unhealthy production finding."""

    code: str
    severity: MonitoringSeverity
    message: str
    worker_id: str | None = None
    entry_id: str | None = None
    job_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionMonitoringSnapshot:
    """Complete dashboard-ready production monitoring snapshot."""

    generated_at: datetime
    queue: QueueProgressSnapshot
    pipeline: PipelineProgressSnapshot
    workers: tuple[WorkerSnapshot, ...]
    metrics: ExecutionMetrics
    diagnostics: tuple[MonitoringDiagnostic, ...]
    events: tuple[ProductionEvent, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionMonitoringConfig:
    """Thresholds controlling worker and stalled-work detection."""

    stale_after_seconds: float = 60.0
    offline_after_seconds: float = 180.0
    stalled_after_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        if self.offline_after_seconds <= self.stale_after_seconds:
            raise ValueError("offline_after_seconds must exceed stale_after_seconds")
        if self.stalled_after_seconds <= 0:
            raise ValueError("stalled_after_seconds must be positive")


class ProductionMonitor:
    """Build monitoring snapshots without mutating production state."""

    def __init__(self, config: ProductionMonitoringConfig | None = None) -> None:
        self.config = config or ProductionMonitoringConfig()

    def snapshot(
        self,
        pipeline: ProductionPipeline,
        queue: RenderQueue,
        workers: tuple[WorkerObservation, ...] = (),
        results: tuple[ExecutionResult, ...] = (),
        events: tuple[ProductionEvent, ...] = (),
        now: datetime | None = None,
    ) -> ProductionMonitoringSnapshot:
        """Build one immutable monitoring snapshot."""
        current = now or datetime.now(UTC)
        worker_snapshots = tuple(
            self._worker_snapshot(observation, current) for observation in workers
        )
        diagnostics = self._diagnostics(queue, worker_snapshots, current)
        ordered_events = tuple(
            sorted(events, key=lambda item: (item.occurred_at, item.event_id))
        )
        return ProductionMonitoringSnapshot(
            generated_at=current,
            queue=self._queue_progress(queue),
            pipeline=self._pipeline_progress(pipeline),
            workers=worker_snapshots,
            metrics=self._execution_metrics(results),
            diagnostics=diagnostics,
            events=ordered_events,
        )

    def _worker_snapshot(
        self,
        observation: WorkerObservation,
        now: datetime,
    ) -> WorkerSnapshot:
        age = (now - observation.last_heartbeat_at).total_seconds()
        if age >= self.config.offline_after_seconds:
            health = WorkerHealth.OFFLINE
        elif age >= self.config.stale_after_seconds:
            health = WorkerHealth.STALE
        else:
            health = WorkerHealth.HEALTHY
        lease = observation.active_lease
        if lease is not None and not lease.is_expired(now):
            active_job_id = lease.job_id
            lease_expires_at = lease.expires_at
        else:
            active_job_id = None
            lease_expires_at = None
        return WorkerSnapshot(
            worker_id=observation.worker.worker_id,
            executor_id=observation.worker.executor_id,
            health=health,
            available=health is WorkerHealth.HEALTHY and active_job_id is None,
            last_heartbeat_at=observation.last_heartbeat_at,
            active_job_id=active_job_id,
            lease_expires_at=lease_expires_at,
        )

    @staticmethod
    def _queue_progress(queue: RenderQueue) -> QueueProgressSnapshot:
        counts = Counter(entry.state for entry in queue.entries)
        total = len(queue.entries)
        completed = counts[QueueState.COMPLETED]
        percentage = (completed / total * 100.0) if total else 0.0
        return QueueProgressSnapshot(
            total=total,
            waiting=counts[QueueState.WAITING],
            ready=counts[QueueState.READY],
            claimed=counts[QueueState.CLAIMED],
            running=counts[QueueState.RUNNING],
            retrying=counts[QueueState.RETRYING],
            completed=completed,
            failed=counts[QueueState.FAILED],
            cancelled=counts[QueueState.CANCELLED],
            blocked=counts[QueueState.BLOCKED],
            completion_percentage=percentage,
        )

    @staticmethod
    def _pipeline_progress(pipeline: ProductionPipeline) -> PipelineProgressSnapshot:
        counts = Counter(node.state for node in pipeline.nodes)
        total = len(pipeline.nodes)
        completed = counts[ProductionState.COMPLETED]
        percentage = (completed / total * 100.0) if total else 0.0
        return PipelineProgressSnapshot(
            total=total,
            pending=counts[ProductionState.PENDING],
            ready=counts[ProductionState.READY],
            blocked=counts[ProductionState.BLOCKED],
            running=counts[ProductionState.RUNNING],
            completed=completed,
            failed=counts[ProductionState.FAILED],
            cancelled=counts[ProductionState.CANCELLED],
            completion_percentage=percentage,
        )

    @staticmethod
    def _execution_metrics(results: tuple[ExecutionResult, ...]) -> ExecutionMetrics:
        durations = [
            max(0.0, (result.completed_at - result.started_at).total_seconds())
            for result in results
        ]
        succeeded = sum(result.succeeded for result in results)
        failed = len(results) - succeeded
        failures = Counter(
            result.error_code.value
            for result in results
            if result.error_code is not None
        )
        total = len(results)
        return ExecutionMetrics(
            total_results=total,
            succeeded=succeeded,
            failed=failed,
            success_percentage=(succeeded / total * 100.0) if total else 0.0,
            average_duration_seconds=(sum(durations) / total) if total else 0.0,
            maximum_duration_seconds=max(durations, default=0.0),
            failures_by_code=tuple(sorted(failures.items())),
        )

    def _diagnostics(
        self,
        queue: RenderQueue,
        workers: tuple[WorkerSnapshot, ...],
        now: datetime,
    ) -> tuple[MonitoringDiagnostic, ...]:
        diagnostics: list[MonitoringDiagnostic] = []
        for worker in workers:
            if worker.health is WorkerHealth.STALE:
                diagnostics.append(
                    MonitoringDiagnostic(
                        code="WORKER_HEARTBEAT_STALE",
                        severity=MonitoringSeverity.WARNING,
                        message=f"Worker heartbeat is stale: {worker.worker_id}",
                        worker_id=worker.worker_id,
                        job_id=worker.active_job_id,
                    )
                )
            elif worker.health is WorkerHealth.OFFLINE:
                diagnostics.append(
                    MonitoringDiagnostic(
                        code="WORKER_OFFLINE",
                        severity=MonitoringSeverity.ERROR,
                        message=f"Worker is offline: {worker.worker_id}",
                        worker_id=worker.worker_id,
                        job_id=worker.active_job_id,
                    )
                )
        stalled_before = now - timedelta(seconds=self.config.stalled_after_seconds)
        active_states = {QueueState.CLAIMED, QueueState.RUNNING}
        for entry in queue.entries:
            if entry.state in active_states and entry.updated_at <= stalled_before:
                diagnostics.append(
                    MonitoringDiagnostic(
                        code="QUEUE_ENTRY_STALLED",
                        severity=MonitoringSeverity.ERROR,
                        message=f"Queue entry has not progressed: {entry.entry_id}",
                        entry_id=entry.entry_id,
                        job_id=entry.job_id,
                    )
                )
            if entry.state is QueueState.BLOCKED:
                diagnostics.append(
                    MonitoringDiagnostic(
                        code="QUEUE_ENTRY_BLOCKED",
                        severity=MonitoringSeverity.WARNING,
                        message=f"Queue entry is blocked: {entry.entry_id}",
                        entry_id=entry.entry_id,
                        job_id=entry.job_id,
                    )
                )
        return tuple(diagnostics)
