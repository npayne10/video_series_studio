"""Phase 20.18.2 corrective acceptance for ProductionTask scheduling priority."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionResource,
    ProductionScheduleReviewDecision,
    ProductionSchedulingUiError,
    ProductionSchedulingUiService,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import (
    ApplicationContext,
    BootstrapOptions,
    StartupMode,
    build_application_context,
)
from vscs.infrastructure.production.schedule_repository import JsonProductionScheduleRepository
from vscs.infrastructure.production.task_repository import JsonProductionTaskRepository

_NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
_SHOT_ID = "EP-001-SCN-001-SHT-002"


def _task(
    task_id: str,
    shot_id: str,
    *,
    created_at: datetime,
    state: ProductionTaskState = ProductionTaskState.PLANNED,
    priority: ProductionTaskPriority = ProductionTaskPriority.NORMAL,
) -> ProductionTask:
    return ProductionTask(
        task_id=task_id,
        production_id="PROD-PRIORITY",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{shot_id}",
            revision=1,
            fingerprint=f"authority-{task_id}",
            approved=True,
            approved_by="planner",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        priority=priority,
        state=state,
        created_at=created_at,
    )


def _service(tmp_path: Path) -> ProductionSchedulingUiService:
    task_root = tmp_path / "tasks"
    schedule_root = tmp_path / "schedules"
    return ProductionSchedulingUiService(
        lambda: JsonProductionTaskRepository(task_root),
        lambda: JsonProductionScheduleRepository(schedule_root),
    )


def test_priority_change_is_persisted_and_drives_next_schedule_revision(tmp_path: Path) -> None:
    service = _service(tmp_path)
    older = _task(
        "PT-VIDEO-GENERATION-SHT001",
        "EP-001-SCN-001-SHT-001",
        created_at=_NOW,
    )
    target = _task(
        "PT-VIDEO-GENERATION-SHT002",
        _SHOT_ID,
        created_at=_NOW + timedelta(minutes=1),
    )
    service.register_compiled_tasks((older, target))
    service.refresh_readiness("PROD-PRIORITY")
    service.register_resource(
        ProductionResource(
            resource_id="LOCAL-GPU-01",
            capabilities=frozenset({ProductionCapability.VIDEO_GENERATION}),
        )
    )

    revision_1 = service.create_schedule_revision("PROD-PRIORITY")
    assert revision_1.schedule.assignments[0].task_id == older.task_id
    service.review_current(
        "PROD-PRIORITY",
        decision=ProductionScheduleReviewDecision.APPROVED,
        reviewed_by="operator",
        notes="Baseline scheduling decision.",
    )
    service.compile_queue("PROD-PRIORITY")
    assert service.queue("PROD-PRIORITY") is not None

    updated = service.update_task_priority(target.task_id, ProductionTaskPriority.HIGH)

    assert updated.priority is ProductionTaskPriority.HIGH
    persisted = {task.task_id: task for task in service.tasks("PROD-PRIORITY")}
    assert persisted[target.task_id].priority is ProductionTaskPriority.HIGH
    assert service.queue("PROD-PRIORITY") is None

    latest_before_reschedule = service.latest_schedule("PROD-PRIORITY")
    assert latest_before_reschedule is not None
    assert latest_before_reschedule.revision == 1
    assert latest_before_reschedule.schedule.assignments[0].task_id == older.task_id

    revision_2 = service.create_schedule_revision("PROD-PRIORITY")
    assert revision_2.revision == 2
    assert revision_2.schedule.assignments[0].task_id == target.task_id
    assert revision_2.schedule.assignments[0].priority is ProductionTaskPriority.HIGH
    assert revision_2.schedule.deferrals[0].task_id == older.task_id
    assert revision_2.schedule.deferrals[0].reason.value == "resource_already_assigned"


def test_operator_priority_survives_recompilation_of_same_governed_contract(tmp_path: Path) -> None:
    service = _service(tmp_path)
    compiled = _task(
        "PT-VIDEO-GENERATION-SHT002",
        _SHOT_ID,
        created_at=_NOW,
    )

    service.register_compiled_tasks((compiled,))
    service.update_task_priority(compiled.task_id, ProductionTaskPriority.HIGH)
    service.register_compiled_tasks((compiled,))

    persisted = service.tasks("PROD-PRIORITY")
    assert len(persisted) == 1
    assert persisted[0].priority is ProductionTaskPriority.HIGH


@pytest.mark.parametrize(
    "state",
    (
        ProductionTaskState.RUNNING,
        ProductionTaskState.COMPLETED,
        ProductionTaskState.CANCELLED,
        ProductionTaskState.SUPERSEDED,
    ),
)
def test_priority_change_is_blocked_after_execution_authority_crosses_boundary(
    tmp_path: Path,
    state: ProductionTaskState,
) -> None:
    service = _service(tmp_path)
    task = _task(
        "PT-TERMINAL",
        _SHOT_ID,
        created_at=_NOW,
        state=state,
    )
    service.register_compiled_tasks((task,))

    with pytest.raises(ProductionSchedulingUiError, match="cannot be changed"):
        service.update_task_priority(task.task_id, ProductionTaskPriority.HIGH)


@pytest.fixture
def application_context(tmp_path: Path) -> Iterator[ApplicationContext]:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        yield context
    finally:
        context.shutdown()


def _scope_workspace(workspace: object) -> None:
    workspace._selected_shot_id = _SHOT_ID  # type: ignore[attr-defined]
    workspace.production_task_production_id.setText("PROD-PRIORITY")  # type: ignore[attr-defined]


def test_priority_control_updates_table_and_persists_across_workspace_reload(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
    application_context: ApplicationContext,
) -> None:
    projects = application_context.services.require(ProjectService)
    projects.create(tmp_path / "Project", name="Project")

    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    workspace = window.production_package_workspace
    _scope_workspace(workspace)

    task = _task(
        "PT-VIDEO-GENERATION-SHT002",
        _SHOT_ID,
        created_at=_NOW,
    )
    workspace.production_scheduling.register_compiled_tasks((task,))
    workspace.production_scheduling.refresh_readiness("PROD-PRIORITY")
    workspace._refresh_production_tasks()

    assert workspace.production_task_table.rowCount() == 1
    assert workspace.production_task_table.item(0, 2).text() == "ready"
    assert workspace.production_task_table.item(0, 9).text() == "NORMAL"

    workspace.production_task_table.selectRow(0)
    qapp.processEvents()
    high_index = workspace.production_task_priority_combo.findData(int(ProductionTaskPriority.HIGH))
    assert high_index >= 0
    workspace.production_task_priority_combo.setCurrentIndex(high_index)
    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.production_task_priority_apply_button,
        Qt.MouseButton.LeftButton,
    )

    persisted = workspace.production_scheduling.tasks("PROD-PRIORITY")
    assert persisted[0].priority is ProductionTaskPriority.HIGH
    assert workspace.production_task_table.item(0, 9).text() == "HIGH"
    assert "NORMAL -> HIGH" in workspace.production_task_readiness_status.text()
    assert "new schedule revision" in workspace.production_task_readiness_status.text()

    second_window = application_context.create_main_window()
    qtbot.addWidget(second_window)  # type: ignore[attr-defined]
    second_workspace = second_window.production_package_workspace
    _scope_workspace(second_workspace)
    second_workspace._refresh_production_tasks()

    assert second_workspace.production_task_table.rowCount() == 1
    assert second_workspace.production_task_table.item(0, 9).text() == "HIGH"
