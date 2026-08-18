"""Integration coverage for durable ProductionSchedule review governance."""

from datetime import UTC, datetime

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionSchedulePersistenceService,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewService,
    ProductionScheduleReviewState,
    ProductionSchedulingService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.infrastructure.production import (
    JsonProductionScheduleRepository,
    JsonProductionTaskRepository,
)

_NOW = datetime(2026, 8, 18, 10, 0, tzinfo=UTC)


def _task(task_id: str, priority: ProductionTaskPriority) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="PROD-001",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{task_id}",
            revision=1,
            fingerprint=f"fingerprint-{task_id}",
            approved=True,
            approved_by="tester",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        priority=priority,
        state=ProductionTaskState.READY,
        created_at=_NOW,
    )


def test_schedule_revision_and_review_survive_repository_reopen_without_task_mutation(
    tmp_path,
) -> None:
    task_repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    high = _task("PT-HIGH", ProductionTaskPriority.HIGH)
    normal = _task("PT-NORMAL", ProductionTaskPriority.NORMAL)
    task_repository.save(high)
    task_repository.save(normal)
    resources = ProductionResourceCatalog(
        (
            ProductionResource(
                resource_id="RESOURCE-A",
                capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
            ),
        )
    )
    scheduling = ProductionSchedulingService(task_repository, resources)
    schedule_root = tmp_path / "production_schedules"
    schedule_repository = JsonProductionScheduleRepository(schedule_root)
    persistence = ProductionSchedulePersistenceService(scheduling, schedule_repository)
    review_service = ProductionScheduleReviewService(schedule_repository)

    snapshot = persistence.create_revision("PROD-001", now=_NOW)
    review = review_service.review(
        snapshot.schedule_id,
        snapshot.revision,
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="Neill",
        notes="Approved for downstream execution planning",
        now=_NOW,
    )

    reopened = JsonProductionScheduleRepository(schedule_root)
    reopened_review = ProductionScheduleReviewService(reopened)
    persisted = reopened.get_snapshot(snapshot.schedule_id, snapshot.revision)
    view = reopened_review.view(snapshot.schedule_id, snapshot.revision)

    assert persisted == snapshot
    assert view.review == review
    assert view.state is ProductionScheduleReviewState.APPROVED
    assert reopened.latest_for_production("PROD-001") == snapshot
    assert task_repository.get("PT-HIGH") == high
    assert task_repository.get("PT-NORMAL") == normal
