"""UI gates for Phase 20.18.2.3.6.6b.5 accepted-provider reconciliation."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
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

SHOT_ID = "EP-001-SCN-001-SHT-002"
TASK_ID = "PT-VIDEO-GENERATION-29A500F54E418255"


@pytest.fixture
def application_context(tmp_path: object) -> Iterator[ApplicationContext]:
    from pathlib import Path

    root = Path(str(tmp_path))
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=root / "settings.yaml",
            plugin_root=root / "plugins",
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
        task_id=TASK_ID,
        production_id="VSCS TSR2",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=SHOT_ID,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id=f"UPD-{SHOT_ID}",
            revision=1,
            fingerprint="ui-authority-fingerprint",
            approved=True,
            approved_by="Neill Payne",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.READY,
    )


def test_production_tasks_exposes_fail_closed_accepted_provider_action(
    qtbot: object,
    qapp: QApplication,
    tmp_path: object,
    application_context: ApplicationContext,
) -> None:
    from pathlib import Path

    root = Path(str(tmp_path))
    projects = application_context.services.require(ProjectService)
    projects.create(root / "Project", name="Project")

    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    workspace = window.production_package_workspace
    workspace._selected_shot_id = SHOT_ID
    workspace.production_task_production_id.setText("VSCS TSR2")
    workspace.production_scheduling.register_compiled_tasks((_task(),))
    workspace._refresh_production_tasks()
    workspace.production_task_table.selectRow(0)
    qapp.processEvents()

    button = workspace.production_task_reconcile_accepted_provider_button
    assert button.text() == "Reconcile Accepted Provider Production"
    assert not button.isEnabled()
    assert "functional-acceptance" in button.toolTip().casefold()

    workspace._accepted_provider_reconciliation_service = lambda: SimpleNamespace(
        assess=lambda _task_id: SimpleNamespace(
            already_reconciled=False,
            eligible=True,
            findings=(),
        )
    )
    workspace._refresh_accepted_provider_reconciliation_eligibility()

    assert button.isEnabled()
    assert "without rerendering" in button.toolTip()
