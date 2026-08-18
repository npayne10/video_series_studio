"""Focused application-service tests for Phase 19.6.11 Production Scheduling UI."""

from datetime import UTC, datetime

import pytest

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewState,
    ProductionSchedulingUiService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository

_NOW = datetime(2026, 8, 18, 11, 0, tzinfo=UTC)


def _task() -> ProductionTask:
    return ProductionTask(
        task_id="PT-UI-001",
        production_id="PROD-UI",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-UI-001",
            revision=1,
            fingerprint="authority-ui-001",
            approved=True,
            approved_by="planner",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.PLANNED,
        created_at=_NOW,
    )


def _service(tmp_path) -> ProductionSchedulingUiService:
    task_root = tmp_path / "tasks"
    schedule_root = tmp_path / "schedules"
    return ProductionSchedulingUiService(
        lambda: JsonProductionTaskRepository(task_root),
        lambda: JsonProductionScheduleRepository(schedule_root),
    )


def test_ui_service_persists_compiler_output_and_schedules_ready_task(tmp_path) -> None:
    service = _service(tmp_path)
    task = _task()
    service.register_resource(
        ProductionResource(
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )

    service.register_compiled_tasks((task,))
    refresh = service.refresh_readiness("PROD-UI")
    snapshot = service.create_schedule_revision("PROD-UI")

    assert len(refresh.transitions) == 1
    persisted = service.tasks("PROD-UI")[0]
    assert persisted.state is ProductionTaskState.READY
    assert snapshot.revision == 1
    assert snapshot.schedule.assignments[0].task_id == task.task_id
    assert snapshot.schedule.assignments[0].resource_id == "GPU-01"


def test_queue_compilation_remains_human_review_gated(tmp_path) -> None:
    service = _service(tmp_path)
    service.register_resource(
        ProductionResource(
            resource_id="GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )
    service.register_compiled_tasks((_task(),))
    service.refresh_readiness("PROD-UI")
    service.create_schedule_revision("PROD-UI")

    with pytest.raises(ValueError, match="review decision"):
        service.compile_queue("PROD-UI")

    review = service.review_current(
        "PROD-UI",
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="operator",
        notes="Resource assignment reviewed and approved.",
    )
    view = service.review_view("PROD-UI")
    queue = service.compile_queue("PROD-UI")

    assert review.reviewed_by == "operator"
    assert view is not None
    assert view.state is ProductionScheduleReviewState.APPROVED
    assert len(queue.entries) == 1
    assert queue.entries[0].task_id == "PT-UI-001"
    assert queue.entries[0].state.value == "ready"


def test_register_compiled_tasks_is_idempotent_for_same_governed_contract(tmp_path) -> None:
    service = _service(tmp_path)
    task = _task()

    service.register_compiled_tasks((task,))
    service.register_compiled_tasks((task,))

    assert service.tasks("PROD-UI") == (task,)
