"""Provider-neutral restart adoption primitives for Phase 20.16."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import uuid4

from vscs.application.production_tasks import (
    ProductionExecutionLease,
    ProductionLeaseManager,
    ProductionQueue,
    ProductionQueueAttempt,
    ProductionQueueState,
    ProductionTask,
    ProductionWorker,
)


class ProductionRestartRecoveryError(RuntimeError):
    """Raised when durable provider work cannot be safely adopted after restart."""


class RestartRecoveryLeaseManager(ProductionLeaseManager):
    """Create a fresh lease identity when adopting already-submitted provider work."""

    def acquire_recovery(
        self,
        queue: ProductionQueue,
        entry_id: str,
        worker_id: str,
        *,
        duration_seconds: float,
        now: datetime | None = None,
    ) -> ProductionExecutionLease:
        entry = queue.entry(entry_id)
        if entry is None:
            raise ProductionRestartRecoveryError(
                f"ProductionQueue entry not found for restart recovery: {entry_id}"
            )
        provisional = super().acquire(
            queue,
            entry,
            worker_id,
            duration_seconds=duration_seconds,
            now=now,
        )
        super().release(provisional.lease_id)
        recovery = replace(
            provisional,
            lease_id=(
                f"PRLEASE-{queue.queue_id}-{entry.entry_id}-{worker_id}-"
                f"{uuid4().hex.upper()}"
            ),
        )
        # ProductionLeaseManager deliberately owns an in-memory map. A recovery lease is
        # still session-scoped authority, but must never masquerade as the old durable lease.
        self._leases[recovery.lease_id] = recovery
        return recovery


@dataclass(frozen=True, slots=True)
class RestartRecoveryAdoption:
    """Fresh session queue/lease authority for one already-submitted provider attempt."""

    queue: ProductionQueue
    lease: ProductionExecutionLease


class RestartRecoveryQueueAdopter:
    """Adopt verified durable provider work into a freshly compiled session queue."""

    def __init__(self, leases: RestartRecoveryLeaseManager) -> None:
        self.leases = leases

    def adopt(
        self,
        queue: ProductionQueue,
        task: ProductionTask,
        worker: ProductionWorker,
        attempts: tuple[ProductionQueueAttempt, ...],
        *,
        lease_duration_seconds: float,
        now: datetime | None = None,
    ) -> RestartRecoveryAdoption:
        current = now or datetime.now(UTC)
        entry = queue.entry_for_task(task.task_id)
        if entry is None:
            raise ProductionRestartRecoveryError(
                f"ProductionTask is not present in current approved queue: {task.task_id}"
            )
        if entry.state is not ProductionQueueState.READY:
            raise ProductionRestartRecoveryError(
                f"Restart recovery requires a freshly compiled READY queue entry: {entry.entry_id}"
            )
        if entry.resource_id != worker.resource_id:
            raise ProductionRestartRecoveryError(
                "Recovery worker resource does not match current approved schedule"
            )
        if not frozenset(task.capabilities).issubset(worker.capabilities):
            raise ProductionRestartRecoveryError(
                "Recovery worker lacks current ProductionTask capabilities"
            )
        self._validate_attempts(entry.maximum_attempts, attempts, worker.worker_id)
        lease = self.leases.acquire_recovery(
            queue,
            entry.entry_id,
            worker.worker_id,
            duration_seconds=lease_duration_seconds,
            now=current,
        )
        recovered_entry = replace(
            entry,
            state=ProductionQueueState.RUNNING,
            attempts=attempts,
            claimed_by=worker.worker_id,
            available_at=None,
            updated_at=current,
        )
        recovered_queue = replace(
            queue,
            entries=tuple(
                recovered_entry if candidate.entry_id == entry.entry_id else candidate
                for candidate in queue.entries
            ),
        )
        return RestartRecoveryAdoption(recovered_queue, lease)

    @staticmethod
    def _validate_attempts(
        maximum_attempts: int,
        attempts: tuple[ProductionQueueAttempt, ...],
        current_worker_id: str,
    ) -> None:
        if not attempts:
            raise ProductionRestartRecoveryError(
                "Restart recovery requires durable attempt history"
            )
        if len(attempts) > maximum_attempts:
            raise ProductionRestartRecoveryError(
                "Durable attempt history exceeds current ProductionTask attempt policy"
            )
        expected = tuple(range(1, len(attempts) + 1))
        actual = tuple(attempt.attempt_number for attempt in attempts)
        if actual != expected:
            raise ProductionRestartRecoveryError(
                "Durable execution attempts are not contiguous from attempt 1"
            )
        if attempts[-1].completed_at is not None:
            raise ProductionRestartRecoveryError(
                "Latest recovered queue attempt must remain active until reconciliation"
            )
        if attempts[-1].worker_id != current_worker_id:
            raise ProductionRestartRecoveryError(
                "Durable execution worker does not match current recovery worker"
            )
        if any(attempt.completed_at is None for attempt in attempts[:-1]):
            raise ProductionRestartRecoveryError(
                "Earlier durable execution attempts must already be terminal"
            )
