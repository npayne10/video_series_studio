"""Integration coverage for Phase 19.6.8 ProductionQueue generalisation."""

from datetime import UTC, datetime

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionQueueCompilerService,
    ProductionQueueState,
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleSnapshot,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
    production_schedule_fingerprint,
)
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


_NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def test_approved_persisted_schedule_compiles_to_general_production_queue(tmp_path) -> None:
    task_repository = JsonProductionTaskRepository(tmp_path / "tasks")
    schedule_repository = JsonProductionScheduleRepository(tmp_path / "schedules")
    task = ProductionTask(
        task_id="PT-AUDIO-001",
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.AUDIO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-AUDIO-001",
            revision=1,
            fingerprint="authority-fingerprint",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(ProductionCapability.AUDIO_GENERATION,),
        expected_outputs=("audio/shot",),
        state=ProductionTaskState.READY,
        created_at=_NOW,
    )
    task_repository.save(task)

    schedule = ProductionSchedule(
        production_id="PROD-001",
        assignments=(
            ProductionScheduleAssignment(
                task_id=task.task_id,
                resource_id="RESOURCE-AUDIO-01",
                priority=task.priority,
                required_capabilities=task.capabilities,
            ),
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
    schedule_repository.save_snapshot(snapshot)
    schedule_repository.append_review(
        ProductionScheduleReviewRecord(
            schedule_id=snapshot.schedule_id,
            production_id=snapshot.production_id,
            revision=snapshot.revision,
            fingerprint=snapshot.fingerprint,
            decision=ProductionScheduleReviewDecision.APPROVED,
            reviewed_by="Neill",
            notes="Approved for queue compilation",
            reviewed_at=_NOW,
        )
    )

    queue = ProductionQueueCompilerService(
        schedule_repository,
        task_repository,
    ).compile("PROD-001", now=_NOW)

    assert queue.production_id == "PROD-001"
    assert queue.schedule_fingerprint == snapshot.fingerprint
    assert len(queue.entries) == 1
    assert queue.entries[0].task_type is ProductionTaskType.AUDIO_GENERATION
    assert queue.entries[0].resource_id == "RESOURCE-AUDIO-01"
    assert queue.entries[0].state is ProductionQueueState.READY
    assert task_repository.get(task.task_id) == task
