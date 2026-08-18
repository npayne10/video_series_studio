"""Focused regression tests for Phase 19.6.9 worker, claim, lease and retry integration."""

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionTask,
    ProductionTaskAttemptPolicy,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerError,
    ProductionWorkerRegistry,
    ProductionWorkerState,
)


_NOW = datetime(2026, 8, 18, 10, 30, tzinfo=UTC)


def _task(
    task_id: str = "PT-001",
    *,
    capability: ProductionCapability = ProductionCapability.VIDEO_GENERATION,
    maximum_attempts: int = 3,
    retry_delay_seconds: int = 0,
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="PROD-001",
        episode_id="EP-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{task_id}",
            revision=1,
            fingerprint=f"fingerprint-{task_id}",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(capability,),
        expected_outputs=("video/shot",),
        priority=ProductionTaskPriority.NORMAL,
        state=ProductionTaskState.READY,
        attempt_policy=ProductionTaskAttemptPolicy(
            maximum_attempts=maximum_attempts,
            retry_delay_seconds=retry_delay_seconds,
        ),
        created_at=_NOW,
    )


def _queue(*tasks: ProductionTask) -> ProductionQueue:
    return ProductionQueue(
        queue_id="PQ-001",
        production_id="PROD-001",
        schedule_id="PS-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=tuple(
            ProductionQueueEntry(
                entry_id=f"PQE-{task.task_id}",
                task_id=task.task_id,
                resource_id=f"RESOURCE-{index:02d}",
                task_type=task.task_type,
                state=ProductionQueueState.READY,
                priority=task.priority,
                maximum_attempts=task.attempt_policy.maximum_attempts,
                retry_delay_seconds=task.attempt_policy.retry_delay_seconds,
                created_at=_NOW,
                updated_at=_NOW,
            )
            for index, task in enumerate(tasks, start=1)
        ),
    )


class _TaskRepository:
    def __init__(self, *tasks: ProductionTask) -> None:
        self.tasks = {task.task_id: task for task in tasks}

    def get(self, task_id: str) -> ProductionTask | None:
        return self.tasks.get(task_id)

    def save(self, task: ProductionTask) -> ProductionTask:
        self.tasks[task.task_id] = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return tuple(
            task for task in self.tasks.values() if task.production_id == production_id
        )


def _runtime(
    *tasks: ProductionTask,
    worker: ProductionWorker | None = None,
) -> ProductionQueueRuntimeService:
    registry = ProductionWorkerRegistry()
    registry.register(
        worker
        or ProductionWorker(
            worker_id="WORKER-01",
            resource_id="RESOURCE-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    return ProductionQueueRuntimeService(_TaskRepository(*tasks), registry)


def test_worker_registry_rejects_duplicate_identity() -> None:
    worker = ProductionWorker(
        worker_id="WORKER-01",
        resource_id="RESOURCE-01",
        capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
    )
    registry = ProductionWorkerRegistry()
    registry.register(worker)

    with pytest.raises(ProductionWorkerError, match="already registered"):
        registry.register(worker)


def test_claim_requires_available_worker_on_scheduled_resource() -> None:
    task = _task()
    queue = _queue(task)
    runtime = _runtime(
        task,
        worker=ProductionWorker(
            worker_id="WORKER-01",
            resource_id="RESOURCE-WRONG",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        ),
    )

    with pytest.raises(ProductionWorkerError, match="scheduled resource"):
        runtime.claim(
            queue,
            "PQE-PT-001",
            "WORKER-01",
            lease_duration_seconds=30,
            now=_NOW,
        )


def test_claim_rejects_worker_without_task_capability() -> None:
    task = _task(capability=ProductionCapability.VOICE_GENERATION)
    queue = _queue(task)
    runtime = _runtime(task)

    with pytest.raises(ProductionWorkerError, match="lacks required"):
        runtime.claim(
            queue,
            "PQE-PT-001",
            "WORKER-01",
            lease_duration_seconds=30,
            now=_NOW,
        )


def test_unavailable_worker_cannot_claim() -> None:
    task = _task()
    queue = _queue(task)
    runtime = _runtime(
        task,
        worker=ProductionWorker(
            worker_id="WORKER-01",
            resource_id="RESOURCE-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
            state=ProductionWorkerState.UNAVAILABLE,
        ),
    )

    with pytest.raises(ProductionWorkerError, match="unavailable"):
        runtime.claim(
            queue,
            "PQE-PT-001",
            "WORKER-01",
            lease_duration_seconds=30,
            now=_NOW,
        )


def test_claim_start_heartbeat_complete_uses_and_releases_lease() -> None:
    task = _task()
    runtime = _runtime(task)
    claim = runtime.claim(
        _queue(task),
        "PQE-PT-001",
        "WORKER-01",
        lease_duration_seconds=30,
        now=_NOW,
    )
    running = runtime.start(
        claim.queue,
        "PQE-PT-001",
        claim.lease.lease_id,
        now=_NOW + timedelta(seconds=1),
    )
    renewed = runtime.heartbeat(
        running,
        "PQE-PT-001",
        claim.lease.lease_id,
        duration_seconds=60,
        now=_NOW + timedelta(seconds=2),
    )
    completed = runtime.complete(
        running,
        "PQE-PT-001",
        claim.lease.lease_id,
        now=_NOW + timedelta(seconds=3),
    )

    assert renewed.expires_at == _NOW + timedelta(seconds=62)
    entry = completed.entry("PQE-PT-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.COMPLETED
    assert entry.attempt_count == 1
    assert runtime.leases.release(claim.lease.lease_id) is None


def test_worker_cannot_hold_two_active_leases() -> None:
    first = _task("PT-001")
    second = _task("PT-002")
    queue = _queue(first, second)
    registry = ProductionWorkerRegistry()
    registry.register(
        ProductionWorker(
            worker_id="WORKER-01",
            resource_id="RESOURCE-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    runtime = ProductionQueueRuntimeService(_TaskRepository(first, second), registry)
    runtime.claim(
        queue,
        "PQE-PT-001",
        "WORKER-01",
        lease_duration_seconds=30,
        now=_NOW,
    )

    second_entry = queue.entry("PQE-PT-002")
    assert second_entry is not None
    with pytest.raises(ProductionWorkerError, match="active lease"):
        runtime.leases.acquire(
            queue,
            second_entry,
            "WORKER-01",
            duration_seconds=30,
            now=_NOW,
        )


def test_expired_claim_returns_to_ready_without_consuming_attempt() -> None:
    task = _task()
    runtime = _runtime(task)
    claim = runtime.claim(
        _queue(task),
        "PQE-PT-001",
        "WORKER-01",
        lease_duration_seconds=10,
        now=_NOW,
    )

    recovered = runtime.recover_expired_leases(
        claim.queue, now=_NOW + timedelta(seconds=10)
    )

    entry = recovered.entry("PQE-PT-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.READY
    assert entry.claimed_by is None
    assert entry.attempt_count == 0


def test_expired_running_lease_uses_retry_policy() -> None:
    task = _task(maximum_attempts=2, retry_delay_seconds=5)
    runtime = _runtime(task)
    claim = runtime.claim(
        _queue(task),
        "PQE-PT-001",
        "WORKER-01",
        lease_duration_seconds=10,
        now=_NOW,
    )
    running = runtime.start(
        claim.queue, "PQE-PT-001", claim.lease.lease_id, now=_NOW
    )

    recovered = runtime.recover_expired_leases(
        running, now=_NOW + timedelta(seconds=10)
    )

    entry = recovered.entry("PQE-PT-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.RETRYING
    assert entry.claimed_by is None
    assert entry.attempt_count == 1
    assert entry.attempts[0].succeeded is False
    assert entry.attempts[0].error_message == "execution lease expired"
    assert entry.available_at == _NOW + timedelta(seconds=15)


def test_expired_running_lease_fails_when_attempts_exhausted() -> None:
    task = _task(maximum_attempts=1)
    runtime = _runtime(task)
    claim = runtime.claim(
        _queue(task),
        "PQE-PT-001",
        "WORKER-01",
        lease_duration_seconds=10,
        now=_NOW,
    )
    running = runtime.start(
        claim.queue, "PQE-PT-001", claim.lease.lease_id, now=_NOW
    )

    recovered = runtime.recover_expired_leases(
        running, now=_NOW + timedelta(seconds=10)
    )

    entry = recovered.entry("PQE-PT-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.FAILED
    assert entry.attempt_count == 1


def test_foreign_lease_cannot_start_another_queue_entry() -> None:
    first = _task("PT-001")
    second = _task("PT-002")
    registry = ProductionWorkerRegistry()
    registry.register(
        ProductionWorker(
            worker_id="WORKER-01",
            resource_id="RESOURCE-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    runtime = ProductionQueueRuntimeService(_TaskRepository(first, second), registry)
    queue = _queue(first, second)
    claim = runtime.claim(
        queue,
        "PQE-PT-001",
        "WORKER-01",
        lease_duration_seconds=30,
        now=_NOW,
    )

    with pytest.raises(ProductionWorkerError, match="does not own"):
        runtime.start(
            claim.queue,
            "PQE-PT-002",
            claim.lease.lease_id,
            now=_NOW + timedelta(seconds=1),
        )
