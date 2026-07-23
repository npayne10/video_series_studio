"""Tests for the initial VSCS application shell."""

from PySide6.QtWidgets import QApplication

from vscs.presentation.windows.main_window import MainWindow


def test_main_window_title(qtbot: object, qapp: QApplication) -> None:
    """The application shell exposes the expected product identity."""
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Video Series Studio" in window.windowTitle()
    assert "VSCS Framework v0.1" in window.windowTitle()
