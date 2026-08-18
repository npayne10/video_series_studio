"""Integration coverage for ProductionQueue worker, lease and retry coordination."""

from datetime import UTC, datetime

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueue,
    ProductionQueueEntry,
    ProductionQueueRuntimeService,
    ProductionQueueState,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    ProductionWorker,
    ProductionWorkerRegistry,
)
from vscs.infrastructure.production import JsonProductionTaskRepository


_NOW = datetime(2026, 8, 18, 10, 45, tzinfo=UTC)


def test_persisted_production_task_can_be_claimed_and_completed_by_matching_worker(
    tmp_path,
) -> None:
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
    workers = ProductionWorkerRegistry()
    workers.register(
        ProductionWorker(
            worker_id="AUDIO-WORKER-01",
            resource_id="AUDIO-NODE-01",
            capabilities=frozenset({ProductionCapability.AUDIO_GENERATION}),
        )
    )
    runtime = ProductionQueueRuntimeService(repository, workers)

    claim = runtime.claim(
        queue,
        "PQE-PT-AUDIO-001",
        "AUDIO-WORKER-01",
        lease_duration_seconds=60,
        now=_NOW,
    )
    running = runtime.start(
        claim.queue,
        "PQE-PT-AUDIO-001",
        claim.lease.lease_id,
        now=_NOW,
    )
    completed = runtime.complete(
        running,
        "PQE-PT-AUDIO-001",
        claim.lease.lease_id,
        now=_NOW,
    )

    entry = completed.entry("PQE-PT-AUDIO-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.COMPLETED
    assert entry.attempts[0].worker_id == "AUDIO-WORKER-01"
    assert repository.get(task.task_id) == task
