"""Provider-neutral monitoring and recovery for ProductionQueue scheduling runtime."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .production_queue import ProductionQueue, ProductionQueueState
from .runtime import (
    ProductionExecutionLease,
    ProductionQueueRuntimeService,
    ProductionWorker,
    ProductionWorkerState,
)


class SchedulingMonitoringSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SchedulingRecoveryAction(StrEnum):
    RELEASE_CLAIM = "release_claim"
    RETRY = "retry"
    FAIL = "fail"


class SchedulingRecoveryReason(StrEnum):
    EXPIRED_LEASE = "expired_lease"


@dataclass(frozen=True, slots=True)
class ProductionQueueProgressSnapshot:
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
class ProductionWorkerRuntimeSnapshot:
    worker_id: str
    resource_id: str
    state: ProductionWorkerState
    active_entry_id: str | None
    active_task_id: str | None
    lease_expires_at: datetime | None
    lease_expired: bool


@dataclass(frozen=True, slots=True)
class SchedulingMonitoringDiagnostic:
    code: str
    severity: SchedulingMonitoringSeverity
    message: str
    entry_id: str | None = None
    task_id: str | None = None
    worker_id: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionSchedulingMonitoringSnapshot:
    generated_at: datetime
    queue_id: str
    production_id: str
    schedule_id: str
    schedule_revision: int
    progress: ProductionQueueProgressSnapshot
    workers: tuple[ProductionWorkerRuntimeSnapshot, ...]
    diagnostics: tuple[SchedulingMonitoringDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class ProductionSchedulingMonitoringConfig:
    stalled_after_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.stalled_after_seconds <= 0:
            raise ValueError("stalled_after_seconds must be positive")


class ProductionSchedulingMonitor:
    """Build immutable provider-neutral monitoring snapshots without mutating runtime state."""

    def __init__(self, config: ProductionSchedulingMonitoringConfig | None = None) -> None:
        self.config = config or ProductionSchedulingMonitoringConfig()

    def snapshot(
        self,
        queue: ProductionQueue,
        *,
        workers: tuple[ProductionWorker, ...] = (),
        leases: tuple[ProductionExecutionLease, ...] = (),
        now: datetime | None = None,
    ) -> ProductionSchedulingMonitoringSnapshot:
        current = now or datetime.now(UTC)
        queue_leases = tuple(lease for lease in leases if lease.queue_id == queue.queue_id)
        workers_by_id = {worker.worker_id: worker for worker in workers}
        active_by_worker = {
            lease.worker_id: lease for lease in queue_leases if not lease.is_expired(current)
        }
        worker_snapshots = tuple(
            self._worker_snapshot(worker, active_by_worker.get(worker.worker_id), current)
            for worker in sorted(workers, key=lambda item: item.worker_id)
        )
        diagnostics = self._diagnostics(
            queue,
            workers_by_id=workers_by_id,
            leases=queue_leases,
            now=current,
        )
        return ProductionSchedulingMonitoringSnapshot(
            generated_at=current,
            queue_id=queue.queue_id,
            production_id=queue.production_id,
            schedule_id=queue.schedule_id,
            schedule_revision=queue.schedule_revision,
            progress=self._progress(queue),
            workers=worker_snapshots,
            diagnostics=diagnostics,
        )

    @staticmethod
    def _worker_snapshot(
        worker: ProductionWorker,
        lease: ProductionExecutionLease | None,
        now: datetime,
    ) -> ProductionWorkerRuntimeSnapshot:
        expired = lease is not None and lease.is_expired(now)
        return ProductionWorkerRuntimeSnapshot(
            worker_id=worker.worker_id,
            resource_id=worker.resource_id,
            state=worker.state,
            active_entry_id=None if lease is None or expired else lease.entry_id,
            active_task_id=None if lease is None or expired else lease.task_id,
            lease_expires_at=None if lease is None else lease.expires_at,
            lease_expired=expired,
        )

    @staticmethod
    def _progress(queue: ProductionQueue) -> ProductionQueueProgressSnapshot:
        counts = Counter(entry.state for entry in queue.entries)
        total = len(queue.entries)
        completed = counts[ProductionQueueState.COMPLETED]
        return ProductionQueueProgressSnapshot(
            total=total,
            waiting=counts[ProductionQueueState.WAITING],
            ready=counts[ProductionQueueState.READY],
            claimed=counts[ProductionQueueState.CLAIMED],
            running=counts[ProductionQueueState.RUNNING],
            retrying=counts[ProductionQueueState.RETRYING],
            completed=completed,
            failed=counts[ProductionQueueState.FAILED],
            cancelled=counts[ProductionQueueState.CANCELLED],
            blocked=counts[ProductionQueueState.BLOCKED],
            completion_percentage=(completed / total * 100.0) if total else 0.0,
        )

    def _diagnostics(
        self,
        queue: ProductionQueue,
        *,
        workers_by_id: dict[str, ProductionWorker],
        leases: tuple[ProductionExecutionLease, ...],
        now: datetime,
    ) -> tuple[SchedulingMonitoringDiagnostic, ...]:
        diagnostics: list[SchedulingMonitoringDiagnostic] = []
        lease_by_entry = {lease.entry_id: lease for lease in leases}
        stalled_before = now - timedelta(seconds=self.config.stalled_after_seconds)

        for entry in sorted(queue.entries, key=lambda item: item.entry_id):
            lease = lease_by_entry.get(entry.entry_id)
            if entry.state in {ProductionQueueState.CLAIMED, ProductionQueueState.RUNNING}:
                if lease is None:
                    diagnostics.append(
                        SchedulingMonitoringDiagnostic(
                            code="QUEUE_ENTRY_ACTIVE_WITHOUT_LEASE",
                            severity=SchedulingMonitoringSeverity.ERROR,
                            message=f"Active queue entry has no execution lease: {entry.entry_id}",
                            entry_id=entry.entry_id,
                            task_id=entry.task_id,
                            worker_id=entry.claimed_by,
                            resource_id=entry.resource_id,
                        )
                    )
                elif lease.is_expired(now):
                    diagnostics.append(
                        SchedulingMonitoringDiagnostic(
                            code="EXECUTION_LEASE_EXPIRED",
                            severity=SchedulingMonitoringSeverity.ERROR,
                            message=f"Execution lease expired for queue entry: {entry.entry_id}",
                            entry_id=entry.entry_id,
                            task_id=entry.task_id,
                            worker_id=lease.worker_id,
                            resource_id=entry.resource_id,
                        )
                    )
                if entry.updated_at <= stalled_before:
                    diagnostics.append(
                        SchedulingMonitoringDiagnostic(
                            code="QUEUE_ENTRY_STALLED",
                            severity=SchedulingMonitoringSeverity.WARNING,
                            message=f"Queue entry has not progressed: {entry.entry_id}",
                            entry_id=entry.entry_id,
                            task_id=entry.task_id,
                            worker_id=entry.claimed_by,
                            resource_id=entry.resource_id,
                        )
                    )
            if entry.claimed_by is not None:
                worker = workers_by_id.get(entry.claimed_by)
                if worker is None:
                    diagnostics.append(
                        SchedulingMonitoringDiagnostic(
                            code="CLAIMED_WORKER_NOT_REGISTERED",
                            severity=SchedulingMonitoringSeverity.ERROR,
                            message=f"Claimed worker is not registered: {entry.claimed_by}",
                            entry_id=entry.entry_id,
                            task_id=entry.task_id,
                            worker_id=entry.claimed_by,
                            resource_id=entry.resource_id,
                        )
                    )
                elif worker.state is ProductionWorkerState.UNAVAILABLE:
                    diagnostics.append(
                        SchedulingMonitoringDiagnostic(
                            code="CLAIMED_WORKER_UNAVAILABLE",
                            severity=SchedulingMonitoringSeverity.WARNING,
                            message=f"Claimed worker is unavailable: {worker.worker_id}",
                            entry_id=entry.entry_id,
                            task_id=entry.task_id,
                            worker_id=worker.worker_id,
                            resource_id=entry.resource_id,
                        )
                    )
            if entry.state is ProductionQueueState.BLOCKED:
                diagnostics.append(
                    SchedulingMonitoringDiagnostic(
                        code="QUEUE_ENTRY_BLOCKED",
                        severity=SchedulingMonitoringSeverity.WARNING,
                        message=f"Queue entry is blocked: {entry.entry_id}",
                        entry_id=entry.entry_id,
                        task_id=entry.task_id,
                        resource_id=entry.resource_id,
                    )
                )
            elif entry.state is ProductionQueueState.FAILED:
                diagnostics.append(
                    SchedulingMonitoringDiagnostic(
                        code="QUEUE_ENTRY_FAILED",
                        severity=SchedulingMonitoringSeverity.ERROR,
                        message=f"Queue entry failed: {entry.entry_id}",
                        entry_id=entry.entry_id,
                        task_id=entry.task_id,
                        resource_id=entry.resource_id,
                    )
                )

        return tuple(diagnostics)


@dataclass(frozen=True, slots=True)
class SchedulingRecoveryDecision:
    entry_id: str
    task_id: str
    worker_id: str
    action: SchedulingRecoveryAction
    reason: SchedulingRecoveryReason
    message: str


@dataclass(frozen=True, slots=True)
class SchedulingRecoveryEvent:
    event_id: str
    occurred_at: datetime
    queue_id: str
    entry_id: str
    task_id: str
    worker_id: str
    action: SchedulingRecoveryAction
    reason: SchedulingRecoveryReason
    message: str


@dataclass(frozen=True, slots=True)
class ProductionSchedulingRecoveryResult:
    queue: ProductionQueue
    decisions: tuple[SchedulingRecoveryDecision, ...]
    events: tuple[SchedulingRecoveryEvent, ...]


class ProductionSchedulingRecoveryService:
    """Recover expired runtime leases using the authoritative 19.6.9 runtime service."""

    def __init__(self, runtime: ProductionQueueRuntimeService) -> None:
        self.runtime = runtime

    def recover_expired(
        self,
        queue: ProductionQueue,
        *,
        now: datetime | None = None,
    ) -> ProductionSchedulingRecoveryResult:
        current = now or datetime.now(UTC)
        expired = self.runtime.leases.expired_for_queue(queue.queue_id, now=current)
        before = {entry.entry_id: entry for entry in queue.entries}
        recovered = self.runtime.recover_expired_leases(queue, now=current)
        decisions: list[SchedulingRecoveryDecision] = []

        for lease in expired:
            previous = before.get(lease.entry_id)
            updated = recovered.entry(lease.entry_id)
            if previous is None or updated is None:
                continue
            if previous.state is ProductionQueueState.CLAIMED and updated.state is ProductionQueueState.READY:
                action = SchedulingRecoveryAction.RELEASE_CLAIM
                message = "Expired claim released back to READY"
            elif previous.state is ProductionQueueState.RUNNING and updated.state in {
                ProductionQueueState.RETRYING,
                ProductionQueueState.READY,
            }:
                action = SchedulingRecoveryAction.RETRY
                message = "Expired running lease recovered through retry policy"
            elif previous.state is ProductionQueueState.RUNNING and updated.state is ProductionQueueState.FAILED:
                action = SchedulingRecoveryAction.FAIL
                message = "Expired running lease exhausted retry policy"
            else:
                continue
            decisions.append(
                SchedulingRecoveryDecision(
                    entry_id=previous.entry_id,
                    task_id=previous.task_id,
                    worker_id=lease.worker_id,
                    action=action,
                    reason=SchedulingRecoveryReason.EXPIRED_LEASE,
                    message=message,
                )
            )

        events = tuple(
            SchedulingRecoveryEvent(
                event_id=f"SCHED-RECOVERY-{current.strftime('%Y%m%d%H%M%S')}-{index:04d}",
                occurred_at=current,
                queue_id=queue.queue_id,
                entry_id=decision.entry_id,
                task_id=decision.task_id,
                worker_id=decision.worker_id,
                action=decision.action,
                reason=decision.reason,
                message=decision.message,
            )
            for index, decision in enumerate(decisions, start=1)
        )
        return ProductionSchedulingRecoveryResult(
            queue=recovered,
            decisions=tuple(decisions),
            events=events,
        )
