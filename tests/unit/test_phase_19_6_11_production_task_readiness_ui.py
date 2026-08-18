"""Qt validation for persisted ProductionTask state and readiness controls."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

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

_NOW = datetime(2026, 8, 18, 13, 45, tzinfo=UTC)
_SHOT_ID = "EP-001-SCN-001-SHT-001"


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
        task_id="PT-READINESS-001",
        production_id="PROD-READINESS",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=_SHOT_ID,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{_SHOT_ID}",
            revision=1,
            fingerprint="authority-readiness-001",
            approved=True,
            approved_by="planner",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.PLANNED,
        created_at=_NOW,
    )


def _scope_workspace(workspace: object) -> None:
    workspace._selected_shot_id = _SHOT_ID  # type: ignore[attr-defined]
    workspace.production_task_production_id.setText("PROD-READINESS")  # type: ignore[attr-defined]


def test_persisted_task_is_reloaded_into_production_tasks_table(
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
    workspace.production_scheduling.register_compiled_tasks((_task(),))
    workspace._refresh_production_tasks()

    assert workspace.production_task_table.rowCount() == 1
    assert workspace.production_task_table.item(0, 2).text() == "planned"

    second_window = application_context.create_main_window()
    qtbot.addWidget(second_window)  # type: ignore[attr-defined]
    second_workspace = second_window.production_package_workspace
    _scope_workspace(second_workspace)
    second_workspace._refresh_production_tasks()

    assert second_workspace.production_task_table.rowCount() == 1
    assert second_workspace.production_task_table.item(0, 0).text() == "PT-READINESS-001"


def test_refresh_task_readiness_updates_authoritative_state_and_table(
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
    workspace.production_scheduling.register_compiled_tasks((_task(),))
    workspace._refresh_production_tasks()

    assert workspace.production_task_refresh_readiness_button.isEnabled()
    qtbot.mouseClick(  # type: ignore[attr-defined]
        workspace.production_task_refresh_readiness_button,
        Qt.MouseButton.LeftButton,
    )

    tasks = workspace.production_scheduling.tasks("PROD-READINESS")
    assert tasks[0].state is ProductionTaskState.READY
    assert workspace.production_task_table.item(0, 2).text() == "ready"
    assert "Current authoritative state: ready" in workspace.production_task_readiness_status.text()
