"""Focused regression tests for Phase 19.6.8 ProductionQueue generalisation."""

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_pipeline import RenderQueue, RenderQueueEntry
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueueCompilerService,
    ProductionQueueEngine,
    ProductionQueueError,
    ProductionQueueState,
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleSnapshot,
    ProductionTask,
    ProductionTaskAttemptPolicy,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
    production_schedule_fingerprint,
)

_NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def _task(
    task_id: str,
    *,
    task_type: ProductionTaskType = ProductionTaskType.VIDEO_GENERATION,
    capability: ProductionCapability = ProductionCapability.VIDEO_GENERATION,
    priority: ProductionTaskPriority = ProductionTaskPriority.NORMAL,
    state: ProductionTaskState = ProductionTaskState.READY,
    maximum_attempts: int = 3,
    retry_delay_seconds: int = 0,
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=task_type,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{task_id}",
            revision=1,
            fingerprint=f"authority-{task_id}",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(capability,),
        expected_outputs=("output/production",),
        priority=priority,
        state=state,
        attempt_policy=ProductionTaskAttemptPolicy(
            maximum_attempts=maximum_attempts,
            retry_delay_seconds=retry_delay_seconds,
        ),
        created_at=_NOW,
    )


class _TaskRepository:
    def __init__(self, tasks: tuple[ProductionTask, ...]) -> None:
        self.tasks = {task.task_id: task for task in tasks}

    def get(self, task_id: str) -> ProductionTask | None:
        return self.tasks.get(task_id)

    def save(self, task: ProductionTask) -> ProductionTask:
        self.tasks[task.task_id] = task
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        return tuple(task for task in self.tasks.values() if task.production_id == production_id)


class _ScheduleRepository:
    def __init__(
        self,
        snapshot: ProductionScheduleSnapshot,
        review: ProductionScheduleReviewRecord | None,
    ) -> None:
        self.snapshot = snapshot
        self.review = review

    def save_snapshot(self, snapshot: ProductionScheduleSnapshot) -> ProductionScheduleSnapshot:
        self.snapshot = snapshot
        return snapshot

    def get_snapshot(self, schedule_id: str, revision: int) -> ProductionScheduleSnapshot | None:
        if self.snapshot.schedule_id == schedule_id and self.snapshot.revision == revision:
            return self.snapshot
        return None

    def history_for_production(self, production_id: str) -> tuple[ProductionScheduleSnapshot, ...]:
        return (self.snapshot,) if self.snapshot.production_id == production_id else ()

    def latest_for_production(self, production_id: str) -> ProductionScheduleSnapshot | None:
        return self.snapshot if self.snapshot.production_id == production_id else None

    def append_review(
        self, review: ProductionScheduleReviewRecord
    ) -> ProductionScheduleReviewRecord:
        self.review = review
        return review

    def reviews(
        self, schedule_id: str, revision: int
    ) -> tuple[ProductionScheduleReviewRecord, ...]:
        if (
            self.review is not None
            and self.review.schedule_id == schedule_id
            and self.review.revision == revision
        ):
            return (self.review,)
        return ()


def _schedule_context(
    tasks: tuple[ProductionTask, ...],
    *,
    decision: ProductionScheduleReviewDecision = ProductionScheduleReviewDecision.APPROVED,
) -> tuple[_ScheduleRepository, _TaskRepository]:
    schedule = ProductionSchedule(
        production_id="PROD-001",
        assignments=tuple(
            ProductionScheduleAssignment(
                task_id=task.task_id,
                resource_id=f"RESOURCE-{index:02d}",
                priority=task.priority,
                required_capabilities=tuple(
                    sorted(task.capabilities, key=lambda capability: capability.value)
                ),
            )
            for index, task in enumerate(tasks, start=1)
        ),
        deferrals=(),
    )
    fingerprint = production_schedule_fingerprint(schedule)
    snapshot = ProductionScheduleSnapshot(
        schedule_id="PS-001",
        production_id="PROD-001",
        revision=1,
        fingerprint=fingerprint,
        schedule=schedule,
        created_at=_NOW,
    )
    review = ProductionScheduleReviewRecord(
        schedule_id=snapshot.schedule_id,
        production_id=snapshot.production_id,
        revision=snapshot.revision,
        fingerprint=snapshot.fingerprint,
        decision=decision,
        reviewed_by="reviewer",
        notes="Reviewed schedule",
        reviewed_at=_NOW,
    )
    return _ScheduleRepository(snapshot, review), _TaskRepository(tasks)


def test_queue_compiles_only_from_approved_schedule() -> None:
    task = _task("PT-001")
    schedules, tasks = _schedule_context(
        (task,), decision=ProductionScheduleReviewDecision.REJECTED
    )

    with pytest.raises(ProductionQueueError, match="not approved"):
        ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)


def test_queue_compiler_rejects_missing_review() -> None:
    task = _task("PT-001")
    schedules, tasks = _schedule_context((task,))
    schedules.review = None

    with pytest.raises(ProductionQueueError, match="exactly one review"):
        ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)


def test_queue_compiler_rejects_task_that_is_no_longer_ready() -> None:
    task = _task("PT-001", state=ProductionTaskState.RUNNING)
    schedules, tasks = _schedule_context((task,))

    with pytest.raises(ProductionQueueError, match="no longer READY"):
        ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)


def test_queue_compiler_rejects_stale_task_priority_after_schedule_review() -> None:
    scheduled_task = _task("PT-001", priority=ProductionTaskPriority.NORMAL)
    schedules, tasks = _schedule_context((scheduled_task,))
    tasks.tasks[scheduled_task.task_id] = _task("PT-001", priority=ProductionTaskPriority.URGENT)

    with pytest.raises(ProductionQueueError, match="authority changed after review"):
        ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)


def test_queue_is_general_across_non_render_production_task_types() -> None:
    task = _task(
        "PT-VOICE",
        task_type=ProductionTaskType.VOICE_GENERATION,
        capability=ProductionCapability.VOICE_GENERATION,
    )
    schedules, tasks = _schedule_context((task,))

    queue = ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)

    assert queue.schedule_id == "PS-001"
    assert queue.schedule_revision == 1
    assert queue.schedule_fingerprint == schedules.snapshot.fingerprint
    assert queue.entries[0].task_id == "PT-VOICE"
    assert queue.entries[0].task_type is ProductionTaskType.VOICE_GENERATION
    assert queue.entries[0].resource_id == "RESOURCE-01"
    assert queue.entries[0].state is ProductionQueueState.READY


def test_queue_preserves_task_priority_and_attempt_policy() -> None:
    task = _task(
        "PT-001",
        priority=ProductionTaskPriority.URGENT,
        maximum_attempts=5,
        retry_delay_seconds=30,
    )
    schedules, tasks = _schedule_context((task,))

    entry = (
        ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW).entries[0]
    )

    assert entry.priority is ProductionTaskPriority.URGENT
    assert entry.maximum_attempts == 5
    assert entry.retry_delay_seconds == 30


def test_queue_engine_orders_ready_entries_by_priority() -> None:
    low = _task("PT-LOW", priority=ProductionTaskPriority.LOW)
    urgent = _task("PT-URGENT", priority=ProductionTaskPriority.URGENT)
    schedules, tasks = _schedule_context((low, urgent))
    queue = ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)

    ready = ProductionQueueEngine().ready_entries(queue, now=_NOW)

    assert tuple(entry.task_id for entry in ready) == ("PT-URGENT", "PT-LOW")


def test_queue_engine_claim_start_and_complete_are_provider_neutral() -> None:
    task = _task("PT-001")
    schedules, tasks = _schedule_context((task,))
    queue = ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)
    engine = ProductionQueueEngine()

    queue = engine.claim(queue, "PQE-PT-001", "WORKER-01", now=_NOW)
    queue = engine.start(queue, "PQE-PT-001", now=_NOW)
    queue = engine.complete(queue, "PQE-PT-001", now=_NOW + timedelta(seconds=5))

    entry = queue.entry("PQE-PT-001")
    assert entry is not None
    assert entry.state is ProductionQueueState.COMPLETED
    assert entry.claimed_by is None
    assert entry.attempt_count == 1
    assert entry.attempts[0].worker_id == "WORKER-01"
    assert entry.attempts[0].succeeded is True


def test_queue_engine_uses_task_retry_policy() -> None:
    task = _task("PT-001", maximum_attempts=2, retry_delay_seconds=10)
    schedules, tasks = _schedule_context((task,))
    queue = ProductionQueueCompilerService(schedules, tasks).compile("PROD-001", now=_NOW)
    engine = ProductionQueueEngine()

    queue = engine.claim(queue, "PQE-PT-001", "WORKER-01", now=_NOW)
    queue = engine.start(queue, "PQE-PT-001", now=_NOW)
    queue = engine.fail(queue, "PQE-PT-001", "temporary failure", now=_NOW)
    retrying = queue.entry("PQE-PT-001")
    assert retrying is not None
    assert retrying.state is ProductionQueueState.RETRYING
    assert retrying.available_at == _NOW + timedelta(seconds=10)

    queue = engine.refresh(queue, now=_NOW + timedelta(seconds=10))
    queue = engine.claim(queue, "PQE-PT-001", "WORKER-02", now=_NOW + timedelta(seconds=10))
    queue = engine.start(queue, "PQE-PT-001", now=_NOW + timedelta(seconds=10))
    queue = engine.fail(
        queue,
        "PQE-PT-001",
        "permanent failure",
        now=_NOW + timedelta(seconds=11),
    )

    failed = queue.entry("PQE-PT-001")
    assert failed is not None
    assert failed.state is ProductionQueueState.FAILED
    assert failed.attempt_count == 2


def test_legacy_render_queue_contract_remains_available_for_compatibility() -> None:
    legacy_entry = RenderQueueEntry(
        entry_id="RQE-001",
        job_id="RJ-001",
        clip_id="CLIP-001",
    )
    legacy_queue = RenderQueue(
        queue_id="RQ-001",
        pipeline_id="PIPE-001",
        entries=(legacy_entry,),
    )

    assert legacy_queue.entry("RQE-001") == legacy_entry
