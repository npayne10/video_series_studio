"""Integration coverage for Phase 19.6.6 ProductionTask scheduling."""

from datetime import UTC, datetime

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionSchedulingDeferralReason,
    ProductionSchedulingService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository


def _task(
    task_id: str,
    *,
    priority: ProductionTaskPriority,
) -> ProductionTask:
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
        created_at=datetime(2026, 8, 18, 8, 0, tzinfo=UTC),
    )


def test_scheduler_uses_persisted_task_authority_without_changing_runtime_state(tmp_path) -> None:
    repository = JsonProductionTaskRepository(tmp_path / "production_tasks")
    high = _task("PT-HIGH", priority=ProductionTaskPriority.HIGH)
    normal = _task("PT-NORMAL", priority=ProductionTaskPriority.NORMAL)
    repository.save(normal)
    repository.save(high)

    catalog = ProductionResourceCatalog(
        (
            ProductionResource(
                resource_id="RESOURCE-A",
                capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
            ),
        )
    )
    service = ProductionSchedulingService(repository, catalog)

    schedule = service.schedule("PROD-001")

    assert schedule.scheduled_task_ids == ("PT-HIGH",)
    assert len(schedule.deferrals) == 1
    assert schedule.deferrals[0].task_id == "PT-NORMAL"
    assert (
        schedule.deferrals[0].reason is ProductionSchedulingDeferralReason.RESOURCE_ALREADY_ASSIGNED
    )
    assert repository.get("PT-HIGH") == high
    assert repository.get("PT-NORMAL") == normal
