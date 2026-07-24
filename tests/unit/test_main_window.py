"""Tests for the VSCS application shell."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import CAPRepository, CAPService
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.plugins import PluginManager
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.windows.main_window import MainWindow


def build_services(tmp_path: Path) -> ApplicationServices:
    """Create application services with isolated configuration and projects."""
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    services = ApplicationServices()
    services.register(ConfigurationService, configuration)

    database = DatabaseManager()
    services.register(DatabaseManager, database)
    projects = ProjectService(configuration, database)
    services.register(ProjectService, projects)
    asset_repository = AssetRepository(database)
    services.register(AssetRepository, asset_repository)
    assets = AssetService(projects, asset_repository)
    services.register(AssetService, assets)
    cap_repository = CAPRepository(database)
    services.register(CAPRepository, cap_repository)
    services.register(CAPService, CAPService(assets, cap_repository))

    plugins = PluginManager(configuration, services, tmp_path / "plugins")
    services.register(PluginManager, plugins)
    plugins.discover()
    return services


def test_main_window_title(qtbot: object, qapp: QApplication, tmp_path: Path) -> None:
    """The application shell exposes the expected product identity."""
    window = MainWindow(build_services(tmp_path))
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Video Series Studio" in window.windowTitle()
    assert "VSCS Framework v0.1" in window.windowTitle()


def test_main_window_opens_default_workspace(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    """The configured default workspace is selected on startup."""
    services = build_services(tmp_path)
    configuration = services.require(ConfigurationService)
    configuration.settings.workspace.default_workspace = "Assets"

    window = MainWindow(services)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.navigation.currentItem().text() == "Assets"
    assert window.content_stack.currentIndex() == 3


def test_main_window_uses_registered_services(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    """The window resolves dependencies through the service container."""
    services = build_services(tmp_path)

    window = MainWindow(services)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.configuration is services.require(ConfigurationService)
    assert window.projects is services.require(ProjectService)
    assert window.assets is services.require(AssetService)
    assert window.caps is services.require(CAPService)
    assert window.plugins is services.require(PluginManager)
    assert window.services is services


def test_project_actions_reflect_active_project(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    """Project actions are enabled only when their lifecycle operation is valid."""
    services = build_services(tmp_path)
    projects = services.require(ProjectService)
    window = MainWindow(services)
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
