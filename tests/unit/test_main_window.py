"""Tests for the VSCS application shell."""

from PySide6.QtWidgets import QApplication

from vscs.presentation.windows.main_window import MainWindow


def test_main_window_title(qtbot: object, qapp: QApplication) -> None:
    """The application shell exposes the expected product identity."""
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert "Video Series Studio" in window.windowTitle()
    assert "VSCS Framework v0.1" in window.windowTitle()


def test_application_shell_starts_on_dashboard(qtbot: object, qapp: QApplication) -> None:
    """The shell starts with Dashboard selected and visible."""
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.navigation.currentItem().text() == "Dashboard"
    assert window.content_stack.currentWidget() is window.dashboard
    assert window.save_project_action.isEnabled() is False


def test_navigation_changes_workspace(qtbot: object, qapp: QApplication) -> None:
    """Selecting a navigation entry changes the active workspace page."""
    window = MainWindow()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.navigation.setCurrentRow(2)

    assert window.navigation.currentItem().text() == "Story"
    assert window.content_stack.currentIndex() == 2
    assert "Story" in window.statusBar().currentMessage()
