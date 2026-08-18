"""Focused tests for Phase 19.6.10 scheduling monitoring and recovery."""

from datetime import UTC, datetime, timedelta

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionLeaseManager,
    ProductionQueue,
    ProductionQueueEngine,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionSchedulingMonitor,
    ProductionSchedulingMonitoringConfig,
    ProductionSchedulingRecoveryService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
    ProductionWorkerState,
    SchedulingRecoveryAction,
)

_NOW = datetime(2026, 8, 18, 11, 0, tzinfo=UTC)


def _task(*, maximum_attempts: int = 3, retry_delay_seconds: int = 0) -> ProductionTask:
    from vscs.application.production_tasks import ProductionTaskAttemptPolicy

    return ProductionTask(
        task_id="PT-001",
        production_id="PROD-001",
        episode_id="EP-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-001",
            revision=1,
            fingerprint="authority-fingerprint",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        priority=ProductionTaskPriority.HIGH,
        state=ProductionTaskState.READY,
        attempt_policy=ProductionTaskAttemptPolicy(
            maximum_attempts=maximum_attempts,
            retry_delay_seconds=retry_delay_seconds,
        ),
        created_at=_NOW,
    )


class _TaskRepository:
    def __init__(self, task: ProductionTask) -> None:
        self.task = task

    def get(self, task_id: str) -> ProductionTask | None:
        return self.task if task_id == self.task.task_id else None

    def save(self, task: ProductionTask) -> ProductionTask:
        self.task = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return (self.task,) if self.task.production_id == production_id else ()


def _queue(
    *,
    state: ProductionQueueState = ProductionQueueState.READY,
    claimed_by: str | None = None,
    maximum_attempts: int = 3,
    retry_delay_seconds: int = 0,
    updated_at: datetime = _NOW,
) -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-001",
        production_id="PROD-001",
        schedule_id="PS-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-001",
                task_id="PT-001",
                resource_id="RESOURCE-01",
                task_type=ProductionTaskType.VIDEO_GENERATION,
                state=state,
                priority=ProductionTaskPriority.HIGH,
                maximum_attempts=maximum_attempts,
                retry_delay_seconds=retry_delay_seconds,
                claimed_by=claimed_by,
                created_at=_NOW,
                updated_at=updated_at,
            ),
        ),
    )


def _worker(state: ProductionWorkerState = ProductionWorkerState.AVAILABLE) -> ProductionWorker:
    return ProductionWorker(
        worker_id="WORKER-01",
        resource_id="RESOURCE-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        state=state,
    )


def _runtime(task: ProductionTask) -> tuple[ProductionQueueRuntimeService, ProductionWorker]:
    registry = ProductionWorkerRegistry()
    worker = _worker()
    registry.register(worker)
    return ProductionQueueRuntimeService(_TaskRepository(task), registry), worker


def test_monitor_reports_provider_neutral_queue_progress() -> None:
    queue = _queue(state=ProductionQueueState.COMPLETED)

    snapshot = ProductionSchedulingMonitor().snapshot(queue, now=_NOW)

    assert snapshot.queue_id == "PQ-001"
    assert snapshot.progress.total == 1
    assert snapshot.progress.completed == 1
    assert snapshot.progress.completion_percentage == 100.0


def test_monitor_detects_active_entry_without_lease() -> None:
    queue = _queue(state=ProductionQueueState.CLAIMED, claimed_by="WORKER-01")

    snapshot = ProductionSchedulingMonitor().snapshot(
        queue, workers=(_worker(),), now=_NOW
    )

    assert "QUEUE_ENTRY_ACTIVE_WITHOUT_LEASE" in {
        diagnostic.code for diagnostic in snapshot.diagnostics
    }


def test_monitor_detects_expired_lease_and_stalled_entry() -> None:
    task = _task()
    runtime, worker = _runtime(task)
    queue = _queue(updated_at=_NOW - timedelta(minutes=30))
    claim = runtime.claim(
        queue,
        "PQE-001",
        worker.worker_id,
        lease_duration_seconds=10,
        now=_NOW - timedelta(minutes=20),
    )

    snapshot = ProductionSchedulingMonitor(
        ProductionSchedulingMonitoringConfig(stalled_after_seconds=60)
    ).snapshot(
        claim.queue,
        workers=(worker,),
        leases=(claim.lease,),
        now=_NOW,
    )

    codes = {diagnostic.code for diagnostic in snapshot.diagnostics}
    assert "EXECUTION_LEASE_EXPIRED" in codes
    assert "QUEUE_ENTRY_STALLED" in codes


def test_monitor_detects_unavailable_claimed_worker() -> None:
    queue = _queue(state=ProductionQueueState.CLAIMED, claimed_by="WORKER-01")

    snapshot = ProductionSchedulingMonitor().snapshot(
        queue,
        workers=(_worker(ProductionWorkerState.UNAVAILABLE),),
        now=_NOW,
    )

    assert "CLAIMED_WORKER_UNAVAILABLE" in {
        diagnostic.code for diagnostic in snapshot.diagnostics
    }


def test_monitor_is_observational_and_does_not_mutate_queue() -> None:
    queue = _queue(state=ProductionQueueState.FAILED)

    ProductionSchedulingMonitor().snapshot(queue, now=_NOW)

    assert queue.entry("PQE-001") is not None
    assert queue.entry("PQE-001").state is ProductionQueueState.FAILED  # type: ignore[union-attr]


def test_recovery_releases_expired_claim_without_consuming_attempt() -> None:
    task = _task()
    runtime, worker = _runtime(task)
    queue = _queue()
    claim = runtime.claim(
        queue,
        "PQE-001",
        worker.worker_id,
        lease_duration_seconds=10,
        now=_NOW,
    )

    result = ProductionSchedulingRecoveryService(runtime).recover_expired(
        claim.queue, now=_NOW + timedelta(seconds=11)
    )

    entry = result.queue.entry("PQE-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.READY
    assert entry.attempt_count == 0
    assert result.decisions[0].action is SchedulingRecoveryAction.RELEASE_CLAIM


def test_recovery_routes_expired_running_lease_through_retry_policy() -> None:
    task = _task(maximum_attempts=2, retry_delay_seconds=30)
    runtime, worker = _runtime(task)
    queue = _queue(maximum_attempts=2, retry_delay_seconds=30)
    claim = runtime.claim(
        queue,
        "PQE-001",
        worker.worker_id,
        lease_duration_seconds=10,
        now=_NOW,
    )
    running = runtime.start(claim.queue, "PQE-001", claim.lease.lease_id, now=_NOW)

    result = ProductionSchedulingRecoveryService(runtime).recover_expired(
        running, now=_NOW + timedelta(seconds=11)
    )

    entry = result.queue.entry("PQE-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.RETRYING
    assert entry.attempt_count == 1
    assert entry.attempts[0].succeeded is False
    assert result.decisions[0].action is SchedulingRecoveryAction.RETRY
    assert result.events[0].entry_id == "PQE-001"


def test_recovery_fails_when_expired_running_lease_exhausts_attempts() -> None:
    task = _task(maximum_attempts=1)
    runtime, worker = _runtime(task)
    queue = _queue(maximum_attempts=1)
    claim = runtime.claim(
        queue,
        "PQE-001",
        worker.worker_id,
        lease_duration_seconds=10,
        now=_NOW,
    )
    running = ProductionQueueEngine().start(
        claim.queue, "PQE-001", now=_NOW
    )

    result = ProductionSchedulingRecoveryService(runtime).recover_expired(
        running, now=_NOW + timedelta(seconds=11)
    )

    entry = result.queue.entry("PQE-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.FAILED
    assert result.decisions[0].action is SchedulingRecoveryAction.FAIL
