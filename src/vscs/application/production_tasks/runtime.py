"""Provider-neutral worker, claim, lease and retry coordination for ProductionQueue."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from .models import ProductionCapability, ProductionTask
from .production_queue import (
    ProductionQueue,
    ProductionQueueEngine,
    ProductionQueueEntry,
    ProductionQueueError,
    ProductionQueueState,
)
from .repository import ProductionTaskRepository


class ProductionWorkerError(ValueError):
    """Raised when worker registration or queue coordination is invalid."""


class ProductionWorkerState(StrEnum):
    """Provider-neutral worker availability."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ProductionWorker:
    """One runtime worker bound to a scheduled production resource."""

    worker_id: str
    resource_id: str
    capabilities: frozenset[ProductionCapability]
    state: ProductionWorkerState = ProductionWorkerState.AVAILABLE
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_text(self.worker_id, "worker_id")
        _require_text(self.resource_id, "resource_id")
        if not self.capabilities:
            raise ValueError("worker capabilities must not be empty")
        keys: set[str] = set()
        for key, value in self.metadata:
            _require_text(key, "metadata key")
            _require_text(value, "metadata value")
            if key in keys:
                raise ValueError("worker metadata cannot contain duplicate keys")
            keys.add(key)


class ProductionWorkerRegistry:
    """Register provider-neutral runtime workers by stable identity."""

    def __init__(self) -> None:
        self._workers: dict[str, ProductionWorker] = {}

    def register(self, worker: ProductionWorker) -> None:
        """Register one worker without replacing an existing identity."""
        if worker.worker_id in self._workers:
            raise ProductionWorkerError(f"ProductionWorker already registered: {worker.worker_id}")
        self._workers[worker.worker_id] = worker

    def get(self, worker_id: str) -> ProductionWorker | None:
        """Return one registered worker."""
        return self._workers.get(worker_id.strip())

    def require(self, worker_id: str) -> ProductionWorker:
        """Return one registered worker or fail with a stable error."""
        normalized = worker_id.strip()
        if not normalized:
            raise ProductionWorkerError("worker_id cannot be blank")
        worker = self._workers.get(normalized)
        if worker is None:
            raise ProductionWorkerError(f"ProductionWorker not found: {normalized}")
        return worker


@dataclass(frozen=True, slots=True)
class ProductionExecutionLease:
    """Time-bound ownership of one ProductionQueue entry by one worker."""

    lease_id: str
    queue_id: str
    entry_id: str
    task_id: str
    worker_id: str
    acquired_at: datetime
    expires_at: datetime
    last_heartbeat_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.lease_id, "lease_id")
        _require_text(self.queue_id, "queue_id")
        _require_text(self.entry_id, "entry_id")
        _require_text(self.task_id, "task_id")
        _require_text(self.worker_id, "worker_id")
        if self.expires_at <= self.acquired_at:
            raise ValueError("lease expiry must be after acquisition")

    def is_expired(self, now: datetime) -> bool:
        """Return whether this lease is expired at the supplied time."""
        return self.expires_at <= now


class ProductionLeaseManager:
    """Manage active in-memory ProductionQueue execution leases."""

    def __init__(self) -> None:
        self._leases: dict[str, ProductionExecutionLease] = {}

    def acquire(
        self,
        queue: ProductionQueue,
        entry: ProductionQueueEntry,
        worker_id: str,
        *,
        duration_seconds: float,
        now: datetime | None = None,
    ) -> ProductionExecutionLease:
        """Acquire exclusive worker and queue-entry ownership."""
        if duration_seconds <= 0:
            raise ProductionWorkerError("lease duration_seconds must be positive")
        normalized_worker = worker_id.strip()
        if not normalized_worker:
            raise ProductionWorkerError("worker_id cannot be blank")
        current = now or datetime.now(UTC)
        self._purge_expired(current)
        if self.active_for_entry(queue.queue_id, entry.entry_id, now=current) is not None:
            raise ProductionWorkerError(f"ProductionQueue entry already leased: {entry.entry_id}")
        if self.active_for_worker(normalized_worker, now=current) is not None:
            raise ProductionWorkerError(f"ProductionWorker already has an active lease: {normalized_worker}")
        lease = ProductionExecutionLease(
            lease_id=f"PLEASE-{queue.queue_id}-{entry.entry_id}-{normalized_worker}",
            queue_id=queue.queue_id,
            entry_id=entry.entry_id,
            task_id=entry.task_id,
            worker_id=normalized_worker,
            acquired_at=current,
            expires_at=current + timedelta(seconds=duration_seconds),
            last_heartbeat_at=current,
        )
        self._leases[lease.lease_id] = lease
        return lease

    def require_active(
        self,
        lease_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionExecutionLease:
        """Return a non-expired active lease."""
        normalized = lease_id.strip()
        if not normalized:
            raise ProductionWorkerError("lease_id cannot be blank")
        lease = self._leases.get(normalized)
        if lease is None:
            raise ProductionWorkerError(f"Production execution lease not found: {normalized}")
        current = now or datetime.now(UTC)
        if lease.is_expired(current):
            raise ProductionWorkerError(f"Production execution lease expired: {normalized}")
        return lease

    def heartbeat(
        self,
        lease_id: str,
        *,
        duration_seconds: float,
        now: datetime | None = None,
    ) -> ProductionExecutionLease:
        """Renew one active lease."""
        if duration_seconds <= 0:
            raise ProductionWorkerError("lease duration_seconds must be positive")
        current = now or datetime.now(UTC)
        lease = self.require_active(lease_id, now=current)
        renewed = replace(
            lease,
            expires_at=current + timedelta(seconds=duration_seconds),
            last_heartbeat_at=current,
        )
        self._leases[lease.lease_id] = renewed
        return renewed

    def release(self, lease_id: str) -> ProductionExecutionLease | None:
        """Release one lease if it is still tracked."""
        return self._leases.pop(lease_id.strip(), None)

    def active_for_entry(
        self,
        queue_id: str,
        entry_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionExecutionLease | None:
        """Return the active lease for one queue entry."""
        current = now or datetime.now(UTC)
        return next(
            (
                lease
                for lease in self._leases.values()
                if lease.queue_id == queue_id
                and lease.entry_id == entry_id
                and not lease.is_expired(current)
            ),
            None,
        )

    def active_for_worker(
        self,
        worker_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionExecutionLease | None:
        """Return the active lease held by one worker."""
        current = now or datetime.now(UTC)
        return next(
            (
                lease
                for lease in self._leases.values()
                if lease.worker_id == worker_id and not lease.is_expired(current)
            ),
            None,
        )

    def expired_for_queue(
        self,
        queue_id: str,
        *,
        now: datetime | None = None,
    ) -> tuple[ProductionExecutionLease, ...]:
        """Return expired leases for one queue without removing them."""
        current = now or datetime.now(UTC)
        return tuple(
            sorted(
                (
                    lease
                    for lease in self._leases.values()
                    if lease.queue_id == queue_id and lease.is_expired(current)
                ),
                key=lambda lease: (lease.expires_at, lease.lease_id),
            )
        )

    def _purge_expired(self, now: datetime) -> None:
        for lease_id in tuple(
            lease.lease_id for lease in self._leases.values() if lease.is_expired(now)
        ):
            self._leases.pop(lease_id, None)


@dataclass(frozen=True, slots=True)
class ProductionQueueClaim:
    """Queue snapshot and lease produced by one successful claim."""

    queue: ProductionQueue
    lease: ProductionExecutionLease


class ProductionQueueRuntimeService:
    """Coordinate workers, claims, leases and retry recovery for ProductionQueue."""

    def __init__(
        self,
        tasks: ProductionTaskRepository,
        workers: ProductionWorkerRegistry,
        leases: ProductionLeaseManager | None = None,
        queue_engine: ProductionQueueEngine | None = None,
    ) -> None:
        self.tasks = tasks
        self.workers = workers
        self.leases = leases or ProductionLeaseManager()
        self.queue_engine = queue_engine or ProductionQueueEngine()

    def claim(
        self,
        queue: ProductionQueue,
        entry_id: str,
        worker_id: str,
        *,
        lease_duration_seconds: float,
        now: datetime | None = None,
    ) -> ProductionQueueClaim:
        """Claim a READY entry only with its scheduled compatible worker resource."""
        current = now or datetime.now(UTC)
        refreshed = self.queue_engine.refresh(queue, current)
        entry = self._require_entry(refreshed, entry_id)
        worker = self.workers.require(worker_id)
        task = self._require_task(entry.task_id)
        if worker.state is not ProductionWorkerState.AVAILABLE:
            raise ProductionWorkerError(f"ProductionWorker is unavailable: {worker.worker_id}")
        if worker.resource_id != entry.resource_id:
            raise ProductionWorkerError(
                f"ProductionWorker resource does not match scheduled resource: {worker.worker_id}"
            )
        if not frozenset(task.capabilities).issubset(worker.capabilities):
            raise ProductionWorkerError(
                f"ProductionWorker lacks required ProductionTask capabilities: {worker.worker_id}"
            )
        lease = self.leases.acquire(
            refreshed,
            entry,
            worker.worker_id,
            duration_seconds=lease_duration_seconds,
            now=current,
        )
        try:
            claimed = self.queue_engine.claim(
                refreshed,
                entry.entry_id,
                worker.worker_id,
                now=current,
            )
        except Exception:
            self.leases.release(lease.lease_id)
            raise
        return ProductionQueueClaim(queue=claimed, lease=lease)

    def start(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Start a claimed entry only while its worker lease remains active."""
        current = now or datetime.now(UTC)
        self._validate_lease(queue, entry_id, lease_id, current)
        return self.queue_engine.start(queue, entry_id, now=current)

    def heartbeat(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        *,
        duration_seconds: float,
        now: datetime | None = None,
    ) -> ProductionExecutionLease:
        """Renew the active lease for a claimed or running entry."""
        current = now or datetime.now(UTC)
        self._validate_lease(queue, entry_id, lease_id, current)
        return self.leases.heartbeat(
            lease_id,
            duration_seconds=duration_seconds,
            now=current,
        )

    def complete(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        *,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Complete a running entry and release its worker lease."""
        current = now or datetime.now(UTC)
        self._validate_lease(queue, entry_id, lease_id, current)
        updated = self.queue_engine.complete(queue, entry_id, now=current)
        self.leases.release(lease_id)
        return updated

    def fail(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        error_message: str,
        *,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Fail a running attempt, release its lease, and apply task retry policy."""
        current = now or datetime.now(UTC)
        self._validate_lease(queue, entry_id, lease_id, current)
        updated = self.queue_engine.fail(queue, entry_id, error_message, now=current)
        self.leases.release(lease_id)
        return updated

    def recover_expired_leases(
        self,
        queue: ProductionQueue,
        *,
        now: datetime | None = None,
    ) -> ProductionQueue:
        """Recover expired claims and running attempts through deterministic retry rules."""
        current = now or datetime.now(UTC)
        updated = queue
        for lease in self.leases.expired_for_queue(queue.queue_id, now=current):
            entry = updated.entry(lease.entry_id)
            if entry is None or entry.claimed_by != lease.worker_id:
                self.leases.release(lease.lease_id)
                continue
            if entry.state is ProductionQueueState.CLAIMED:
                updated = self.queue_engine.release_claim(updated, entry.entry_id, now=current)
            elif entry.state is ProductionQueueState.RUNNING:
                updated = self.queue_engine.fail(
                    updated,
                    entry.entry_id,
                    "execution lease expired",
                    now=current,
                )
            self.leases.release(lease.lease_id)
        return self.queue_engine.refresh(updated, current)

    def _validate_lease(
        self,
        queue: ProductionQueue,
        entry_id: str,
        lease_id: str,
        now: datetime,
    ) -> ProductionExecutionLease:
        lease = self.leases.require_active(lease_id, now=now)
        entry = self._require_entry(queue, entry_id)
        if lease.queue_id != queue.queue_id or lease.entry_id != entry.entry_id:
            raise ProductionWorkerError("Production execution lease does not own this queue entry")
        if lease.task_id != entry.task_id or lease.worker_id != entry.claimed_by:
            raise ProductionWorkerError("Production execution lease ownership does not match queue state")
        return lease

    def _require_task(self, task_id: str) -> ProductionTask:
        task = self.tasks.get(task_id)
        if task is None:
            raise ProductionWorkerError(f"ProductionTask not found for queue entry: {task_id}")
        return task

    @staticmethod
    def _require_entry(queue: ProductionQueue, entry_id: str) -> ProductionQueueEntry:
        entry = queue.entry(entry_id)
        if entry is None:
            raise ProductionQueueError(f"ProductionQueue entry not found: {entry_id}")
        return entry


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")
