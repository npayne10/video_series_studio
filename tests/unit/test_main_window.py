"""Tests for the VSCS application shell."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.infrastructure.configuration import ConfigurationService
from vscs.presentation.windows.main_window import MainWindow


def test_main_window_title(qtbot: object, qapp: QApplication, tmp_path: Path) -> None:
    """The application shell exposes the expected product identity."""
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    window = MainWindow(configuration)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Video Series Studio" in window.windowTitle()
    assert "VSCS Framework v0.1" in window.windowTitle()


def test_main_window_opens_default_workspace(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    """The configured default workspace is selected on startup."""
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    configuration.settings.workspace.default_workspace = "Assets"

    window = MainWindow(configuration)
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.navigation.currentItem().text() == "Assets"
    assert window.content_stack.currentIndex() == 3
