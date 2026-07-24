"""Tests for the VSCS application shell."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.windows.main_window import MainWindow


def build_services(tmp_path: Path) -> ApplicationServices:
    """Create application services with an isolated configuration."""
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    services = ApplicationServices()
    services.register(ConfigurationService, configuration)
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


def test_main_window_uses_registered_configuration(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    """The window resolves its configuration through the service container."""
    services = build_services(tmp_path)

    window = MainWindow(services)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.configuration is services.require(ConfigurationService)
    assert window.services is services
