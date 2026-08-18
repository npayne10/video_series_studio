"""Focused regression tests for Phase 19.6.6 provider-neutral scheduling."""

from datetime import UTC, datetime, timedelta

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionResourceCatalog,
    ProductionResourceState,
    ProductionScheduler,
    ProductionSchedulingDeferralReason,
    ProductionSchedulingError,
    ProductionSchedulingService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)

_BASE_TIME = datetime(2026, 8, 18, 8, 0, tzinfo=UTC)


def _task(
    task_id: str,
    *,
    state: ProductionTaskState = ProductionTaskState.READY,
    priority: ProductionTaskPriority = ProductionTaskPriority.NORMAL,
    capabilities: tuple[ProductionCapability, ...] = (ProductionCapability.VIDEO_GENERATION,),
    created_at: datetime = _BASE_TIME,
    production_id: str = "PROD-001",
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id=production_id,
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
        capabilities=capabilities,
        expected_outputs=("video/shot",),
        priority=priority,
        state=state,
        created_at=created_at,
    )


def _resource(
    resource_id: str,
    *capabilities: ProductionCapability,
    state: ProductionResourceState = ProductionResourceState.AVAILABLE,
) -> ProductionResource:
    return ProductionResource(
        resource_id=resource_id,
        capabilities=frozenset(capabilities or (ProductionCapability.VIDEO_GENERATION,)),
        state=state,
    )


def test_scheduler_rejects_blank_or_mixed_production_scope() -> None:
    scheduler = ProductionScheduler()
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"),))

    with pytest.raises(ProductionSchedulingError, match="production_id cannot be blank"):
        scheduler.build(" ", (_task("PT-A"),), catalog)

    with pytest.raises(ProductionSchedulingError, match="different productions"):
        scheduler.build(
            "PROD-001",
            (_task("PT-A"), _task("PT-B", production_id="PROD-002")),
            catalog,
        )


def test_scheduler_only_considers_ready_tasks_without_mutating_lifecycle() -> None:
    ready = _task("PT-READY")
    planned = _task("PT-PLANNED", state=ProductionTaskState.PLANNED)
    completed = _task("PT-COMPLETE", state=ProductionTaskState.COMPLETED)
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"),))

    schedule = ProductionScheduler().build("PROD-001", (planned, ready, completed), catalog)

    assert schedule.scheduled_task_ids == ("PT-READY",)
    assert schedule.ignored_task_ids == ("PT-COMPLETE", "PT-PLANNED")
    assert ready.state is ProductionTaskState.READY
    assert planned.state is ProductionTaskState.PLANNED
    assert completed.state is ProductionTaskState.COMPLETED


def test_scheduler_orders_ready_tasks_by_priority_before_age() -> None:
    older_normal = _task(
        "PT-NORMAL",
        priority=ProductionTaskPriority.NORMAL,
        created_at=_BASE_TIME,
    )
    newer_urgent = _task(
        "PT-URGENT",
        priority=ProductionTaskPriority.URGENT,
        created_at=_BASE_TIME + timedelta(hours=1),
    )
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"), _resource("RESOURCE-B")))

    schedule = ProductionScheduler().build(
        "PROD-001",
        (older_normal, newer_urgent),
        catalog,
    )

    assert schedule.scheduled_task_ids == ("PT-URGENT", "PT-NORMAL")


def test_scheduler_uses_creation_time_then_task_id_as_deterministic_tie_breakers() -> None:
    earlier = _task("PT-C", created_at=_BASE_TIME)
    same_time_b = _task("PT-B", created_at=_BASE_TIME + timedelta(minutes=1))
    same_time_a = _task("PT-A", created_at=_BASE_TIME + timedelta(minutes=1))
    catalog = ProductionResourceCatalog(
        (_resource("RESOURCE-A"), _resource("RESOURCE-B"), _resource("RESOURCE-C"))
    )

    schedule = ProductionScheduler().build(
        "PROD-001",
        (same_time_b, earlier, same_time_a),
        catalog,
    )

    assert schedule.scheduled_task_ids == ("PT-C", "PT-A", "PT-B")


def test_scheduler_selects_first_compatible_resource_deterministically() -> None:
    task = _task(
        "PT-A",
        capabilities=(
            ProductionCapability.VIDEO_GENERATION,
            ProductionCapability.POST_PROCESSING,
        ),
    )
    catalog = ProductionResourceCatalog(
        (
            _resource(
                "RESOURCE-B",
                ProductionCapability.VIDEO_GENERATION,
                ProductionCapability.POST_PROCESSING,
                ProductionCapability.QUALITY_CONTROL,
            ),
            _resource("RESOURCE-A", ProductionCapability.VIDEO_GENERATION),
            _resource(
                "RESOURCE-C",
                ProductionCapability.VIDEO_GENERATION,
                ProductionCapability.POST_PROCESSING,
            ),
        )
    )

    schedule = ProductionScheduler().build("PROD-001", (task,), catalog)

    assert len(schedule.assignments) == 1
    assert schedule.assignments[0].resource_id == "RESOURCE-B"
    assert schedule.assignments[0].required_capabilities == (
        ProductionCapability.POST_PROCESSING,
        ProductionCapability.VIDEO_GENERATION,
    )


def test_scheduler_reports_no_capable_resource() -> None:
    task = _task(
        "PT-A",
        capabilities=(ProductionCapability.VOICE_GENERATION,),
    )
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"),))

    schedule = ProductionScheduler().build("PROD-001", (task,), catalog)

    assert schedule.assignments == ()
    assert schedule.deferrals[0].reason is ProductionSchedulingDeferralReason.NO_CAPABLE_RESOURCE
    assert schedule.deferrals[0].resource_ids == ()


def test_scheduler_distinguishes_unavailable_capable_resources() -> None:
    resource = _resource(
        "RESOURCE-A",
        ProductionCapability.VIDEO_GENERATION,
        state=ProductionResourceState.UNAVAILABLE,
    )
    catalog = ProductionResourceCatalog((resource,))

    schedule = ProductionScheduler().build("PROD-001", (_task("PT-A"),), catalog)

    assert schedule.assignments == ()
    assert schedule.deferrals[0].reason is ProductionSchedulingDeferralReason.NO_AVAILABLE_RESOURCE
    assert schedule.deferrals[0].resource_ids == ("RESOURCE-A",)


def test_scheduler_does_not_double_assign_one_resource_in_same_pass() -> None:
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"),))
    first = _task("PT-A", priority=ProductionTaskPriority.HIGH)
    second = _task("PT-B", priority=ProductionTaskPriority.NORMAL)

    schedule = ProductionScheduler().build("PROD-001", (second, first), catalog)

    assert schedule.scheduled_task_ids == ("PT-A",)
    assert schedule.assignments[0].resource_id == "RESOURCE-A"
    assert len(schedule.deferrals) == 1
    assert schedule.deferrals[0].task_id == "PT-B"
    assert (
        schedule.deferrals[0].reason is ProductionSchedulingDeferralReason.RESOURCE_ALREADY_ASSIGNED
    )
    assert schedule.deferrals[0].resource_ids == ("RESOURCE-A",)


def test_scheduling_service_loads_only_requested_production_and_does_not_execute() -> None:
    class Repository:
        def __init__(self) -> None:
            self.requested: list[str] = []
            self.saved: list[ProductionTask] = []

        def get(self, task_id: str) -> ProductionTask | None:
            return None

        def save(self, task: ProductionTask) -> ProductionTask:
            self.saved.append(task)
            return task

        def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
            self.requested.append(production_id)
            return (_task("PT-A", production_id=production_id),)

    repository = Repository()
    catalog = ProductionResourceCatalog((_resource("RESOURCE-A"),))
    service = ProductionSchedulingService(repository, catalog)

    schedule = service.schedule(" PROD-001 ")

    assert repository.requested == ["PROD-001"]
    assert repository.saved == []
    assert schedule.production_id == "PROD-001"
    assert schedule.scheduled_task_ids == ("PT-A",)
