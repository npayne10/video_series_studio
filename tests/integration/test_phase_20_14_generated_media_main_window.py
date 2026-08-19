from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vscs.application.projects import ProjectService
from vscs.bootstrap import (
    ApplicationContext,
    BootstrapOptions,
    StartupMode,
    build_application_context,
)


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


def test_generated_media_workspace_is_project_scoped_and_navigable(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
    application_context: ApplicationContext,
) -> None:
    projects = application_context.services.require(ProjectService)
    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    matches = window.navigation.findItems("Generated Media", Qt.MatchFlag.MatchExactly)
    assert len(matches) == 1
    assert window._generated_media_ui_service() is None

    projects.create(tmp_path / "Xorix", name="Xorix")
    window._update_project_state()
    window.navigation.setCurrentItem(matches[0])
    qapp.processEvents()

    assert window.content_stack.currentWidget() is window.generated_media_workspace
    assert window._generated_media_ui_service() is not None
    assert window.generated_media_workspace.production_filter.currentText() == "All Productions"
    assert window.generated_media_workspace.episode_filter.currentText() == "All Episodes"
    assert window.generated_media_workspace.task_filter.currentText() == "All Tasks"
    assert "No Generated Media has been ingested" in window.generated_media_workspace.summary.text()
