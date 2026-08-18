"""Qt coverage for Phase 19.6.11 Production Scheduling UI."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
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

_NOW = datetime(2026, 8, 18, 11, 15, tzinfo=UTC)


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


def test_production_planning_installs_scheduling_tab(
    qtbot: object,
    qapp: QApplication,
    application_context: ApplicationContext,
) -> None:
    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    workspace = window.production_package_workspace

    labels = [
        workspace.compiler_tabs.tabText(index)
        for index in range(workspace.compiler_tabs.count())
    ]

    assert "Scheduling" in labels
    assert workspace.findChild(QWidget, "production_scheduling_tab") is not None
    assert workspace.production_scheduling_status is not None
    assert not workspace.scheduling_create_revision_button.isEnabled()
    assert not workspace.scheduling_approve_button.isEnabled()
    assert not workspace.scheduling_compile_queue_button.isEnabled()


def test_operator_can_review_schedule_and_compile_queue_without_execution(
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
    workspace.production_task_production_id.setText("PROD-UI")
    workspace._refresh_production_scheduling()

    workspace.scheduling_resource_id.setText("GPU-01")
    workspace.scheduling_resource_capabilities.setText("video_generation")
    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.scheduling_register_resource_button,
        Qt.MouseButton.LeftButton,
    )
    assert workspace.scheduling_resource_table.rowCount() == 1

    workspace.production_scheduling.register_compiled_tasks((_task(),))
    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.scheduling_refresh_readiness_button,
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.scheduling_create_revision_button,
        Qt.MouseButton.LeftButton,
    )

    assert workspace.scheduling_schedule_table.rowCount() == 1
    assert workspace.scheduling_approve_button.isEnabled()
    assert not workspace.scheduling_compile_queue_button.isEnabled()

    workspace.scheduling_reviewer.setText("operator")
    workspace.scheduling_review_notes.setPlainText(
        "Reviewed task priority and resource assignment."
    )
    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.scheduling_approve_button,
        Qt.MouseButton.LeftButton,
    )

    assert "approved" in workspace.scheduling_review_status.text().lower()
    assert workspace.scheduling_compile_queue_button.isEnabled()

    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.scheduling_compile_queue_button,
        Qt.MouseButton.LeftButton,
    )

    assert workspace.scheduling_queue_table.rowCount() == 1
    assert (
        "external execution has not started"
        in workspace.production_scheduling_status.text().lower()
    )
    queue = workspace.production_scheduling.queue("PROD-UI")
    assert queue is not None
    assert queue.entries[0].state.value == "ready"
