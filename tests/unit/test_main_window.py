"""Tests for the VSCS application shell."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog

from vscs.application.assets import AssetService
from vscs.application.caps import CAPService
from vscs.application.projects import ProjectService
from vscs.bootstrap import (
    ApplicationContext,
    BootstrapOptions,
    StartupMode,
    build_application_context,
)
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.plugins import PluginManager


@pytest.fixture
def application_context(tmp_path: Path) -> Iterator[ApplicationContext]:
    """Build the real Phase 16 application graph for MainWindow tests."""
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


def test_main_window_title(
    qtbot: object,
    qapp: QApplication,
    application_context: ApplicationContext,
) -> None:
    """The application shell exposes the expected product identity."""
    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Video Series Studio" in window.windowTitle()
    assert "VSCS Framework v0.1" in window.windowTitle()


def test_main_window_opens_default_workspace(
    qtbot: object,
    qapp: QApplication,
    application_context: ApplicationContext,
) -> None:
    """The configured default workspace is selected on startup."""
    application_context.configuration.settings.workspace.default_workspace = "Assets"

    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.navigation.currentItem().text() == "Assets"
    assert window.content_stack.currentIndex() == 3


def test_main_window_uses_registered_services(
    qtbot: object,
    qapp: QApplication,
    application_context: ApplicationContext,
) -> None:
    """The window resolves dependencies through the composition root."""
    services = application_context.services

    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.configuration is services.require(ConfigurationService)
    assert window.projects is services.require(ProjectService)
    assert window.assets is services.require(AssetService)
    assert window.caps is services.require(CAPService)
    assert window.plugins is services.require(PluginManager)
    assert window.services is services


def test_project_actions_reflect_active_project(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
    application_context: ApplicationContext,
) -> None:
    """Project actions are enabled only when their lifecycle operation is valid."""
    projects = application_context.services.require(ProjectService)
    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.new_project_action.isEnabled()
    assert not window.save_project_action.isEnabled()
    assert not window.asset_manager.add_button.isEnabled()
    assert not window.cap_manager.add_button.isEnabled()

    projects.create(tmp_path / "Example", name="Example")
    window._update_project_state()

    assert not window.new_project_action.isEnabled()
    assert window.save_project_action.isEnabled()
    assert window.close_project_action.isEnabled()
    assert window.asset_manager.add_button.isEnabled()
    assert window.cap_manager.add_button.isEnabled()
    assert "Example" in window.windowTitle()


def test_create_project_uses_selected_parent_and_keyword_name(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    application_context: ApplicationContext,
) -> None:
    """The New Project action passes the current ProjectService contract."""
    projects = application_context.services.require(ProjectService)
    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("  Test Production  ", True),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args, **kwargs: str(tmp_path),
    )

    window._create_project()

    expected_directory = tmp_path / "Test Production"
    assert projects.current_project is not None
    assert projects.current_project.name == "Test Production"
    assert projects.project_directory == expected_directory.resolve(strict=False)
    assert (expected_directory / ProjectService.PROJECT_FILE_NAME).is_file()
    assert "Created project: Test Production" in window.statusBar().currentMessage()


def test_save_project_uses_active_project_after_void_service_call(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
    application_context: ApplicationContext,
) -> None:
    """Saving through the UI does not expect ProjectService.save to return metadata."""
    projects = application_context.services.require(ProjectService)
    projects.create(tmp_path / "Example", name="Example")
    window = application_context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window._save_project()

    assert "Saved project: Example" in window.statusBar().currentMessage()
