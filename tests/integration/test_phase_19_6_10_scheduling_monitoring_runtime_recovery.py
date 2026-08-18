"""Integration coverage for provider-neutral scheduling monitoring and recovery."""

from datetime import UTC, datetime, timedelta

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionSchedulingMonitor,
    ProductionSchedulingRecoveryService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
    SchedulingRecoveryAction,
)
from vscs.infrastructure.production import JsonProductionTaskRepository

_NOW = datetime(2026, 8, 18, 11, 30, tzinfo=UTC)


def test_persisted_task_runtime_is_monitorable_and_recovers_expired_claim(tmp_path) -> None:
    task = ProductionTask(
        task_id="PT-AUDIO-001",
        production_id="PROD-001",
        episode_id="EP-001",
        task_type=ProductionTaskType.AUDIO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-AUDIO-001",
            revision=1,
            fingerprint="authority-audio-001",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(ProductionCapability.AUDIO_GENERATION,),
        expected_outputs=("audio/shot",),
        priority=ProductionTaskPriority.HIGH,
        state=ProductionTaskState.READY,
        created_at=_NOW,
    )
    repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    repository.save(task)
    queue = ProductionQueue(
        queue_id="PQ-001",
        production_id="PROD-001",
        schedule_id="PS-001",
        schedule_revision=1,
        schedule_fingerprint="schedule-fingerprint",
        entries=(
            ProductionQueueEntry(
                entry_id="PQE-PT-AUDIO-001",
                task_id=task.task_id,
                resource_id="AUDIO-NODE-01",
                task_type=task.task_type,
                state=ProductionQueueState.READY,
                priority=task.priority,
                created_at=_NOW,
                updated_at=_NOW,
            ),
        ),
    )
    worker = ProductionWorker(
        worker_id="AUDIO-WORKER-01",
        resource_id="AUDIO-NODE-01",
        capabilities=frozenset({ProductionCapability.AUDIO_GENERATION}),
    )
    workers = ProductionWorkerRegistry()
    workers.register(worker)
    runtime = ProductionQueueRuntimeService(repository, workers)
    claim = runtime.claim(
        queue,
        "PQE-PT-AUDIO-001",
        worker.worker_id,
        lease_duration_seconds=10,
        now=_NOW,
    )

    monitored = ProductionSchedulingMonitor().snapshot(
        claim.queue,
        workers=(worker,),
        leases=(claim.lease,),
        now=_NOW + timedelta(seconds=11),
    )
    recovered = ProductionSchedulingRecoveryService(runtime).recover_expired(
        claim.queue,
        now=_NOW + timedelta(seconds=11),
    )

    assert "EXECUTION_LEASE_EXPIRED" in {diagnostic.code for diagnostic in monitored.diagnostics}
    entry = recovered.queue.entry("PQE-PT-AUDIO-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.READY
    assert recovered.decisions[0].action is SchedulingRecoveryAction.RELEASE_CLAIM
    assert repository.get(task.task_id) == task
