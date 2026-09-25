"""Qt validation for persisted ProductionTask state and readiness controls."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

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


def test_compile_persists_task_and_refreshes_readiness_immediately(
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

    workspace._refresh_production_task_context = lambda: None
    workspace._production_task_blocker = lambda: ""
    workspace._production_task_context = lambda: object()
    workspace.production_task_compiler.compile_shot = lambda _shot, _context: (_task(),)

    workspace._compile_production_tasks()

    persisted = workspace.production_scheduling.tasks("PROD-READINESS")
    assert len(persisted) == 1
    assert persisted[0].task_id == "PT-READINESS-001"
    assert workspace.production_task_refresh_readiness_button.isEnabled()
    assert (
        "Authoritative persisted ProductionTask state: planned"
        in workspace.production_task_readiness_status.text()
    )


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


def test_current_shot_compilation_context_inherits_previous_video_task_dependency(
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

    predecessor = replace(
        _task(),
        task_id="PT-VIDEO-GENERATION-PREVIOUS",
        shot_id="EP-001-SCN-001-SHT-001",
    )
    workspace.production_scheduling.register_compiled_tasks((predecessor,))
    workspace._selected_shot_id = "EP-001-SCN-001-SHT-002"
    workspace.production_task_production_id.setText("PROD-READINESS")
    workspace.packages.current_package = lambda _shot_id: SimpleNamespace(
        continuity={
            "governed": {
                "previous_shot_id": "EP-001-SCN-001-SHT-001",
            },
            "production": {
                "previous_shot_id": "EP-001-SCN-001-SHT-001",
            },
        }
    )

    dependencies, blocker = workspace._production_task_dependencies()

    assert blocker == ""
    assert dependencies == (predecessor.task_id,)


def test_previous_shot_dependency_reads_governed_fallback_when_production_view_missing(
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

    predecessor = replace(
        _task(),
        task_id="PT-VIDEO-GENERATION-PREVIOUS",
        shot_id="EP-001-SCN-001-SHT-001",
    )
    workspace.production_scheduling.register_compiled_tasks((predecessor,))
    workspace._selected_shot_id = "EP-001-SCN-001-SHT-002"
    workspace.production_task_production_id.setText("PROD-READINESS")
    workspace.packages.current_package = lambda _shot_id: SimpleNamespace(
        continuity={
            "governed": {
                "previous_shot_id": "EP-001-SCN-001-SHT-001",
            }
        }
    )

    dependencies, blocker = workspace._production_task_dependencies()

    assert blocker == ""
    assert dependencies == (predecessor.task_id,)


def test_series_entry_continuity_produces_no_task_dependency(
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

    workspace._selected_shot_id = "EP-001-SCN-001-SHT-001"
    workspace.production_task_production_id.setText("PROD-READINESS")
    workspace.packages.current_package = lambda _shot_id: SimpleNamespace(
        continuity={
            "governed": {"previous_shot_id": ""},
            "production": {"previous_shot_id": ""},
        }
    )

    dependencies, blocker = workspace._production_task_dependencies()

    assert blocker == ""
    assert dependencies == ()


def test_completion_reconciliation_control_enables_only_for_completable_task(
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

    ready = replace(_task(), state=ProductionTaskState.READY)
    workspace.production_scheduling.register_compiled_tasks((ready,))
    workspace._refresh_production_tasks()
    workspace.production_task_table.selectRow(0)
    qapp.processEvents()

    assert workspace.production_task_reconcile_completion_button.isEnabled()
    assert "governed Generated Media" in (
        workspace.production_task_reconcile_completion_button.toolTip()
    )
