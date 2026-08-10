"""Phase 16.2a.8.5.4.5.2.2 keyboard and focus certification."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from tests.certification.keyboard_focus_matrix import (
    KEYBOARD_FOCUS_MATRIX,
    keyboard_focus_areas,
    keyboard_focus_test_nodes,
)
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)

EXPECTED_AREAS = (
    "Welcome keyboard entry",
    "Welcome focus containment",
    "Tour keyboard navigation",
    "Tour focus containment",
    "Try It focus handoff",
    "Uninterrupted identity entry",
    "Focus restoration",
    "Escape recovery",
    "Checklist keyboard activation",
)


def _settings(tmp_path: Path, name: str) -> QSettings:
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


def _show(dialog: GuidedFirstSceneEditorDialog, qapp: QApplication) -> None:
    dialog.show()
    qapp.processEvents()


def _start_guide(
    dialog: GuidedFirstSceneEditorDialog,
    qapp: QApplication,
) -> None:
    _show(dialog, qapp)
    QTest.keyClick(dialog.welcome_overlay.start_button, Qt.Key.Key_Return)
    qapp.processEvents()
    assert dialog.tour_overlay.isVisible()


def _is_descendant(widget: QWidget | None, ancestor: QWidget) -> bool:
    current = widget
    while current is not None:
        if current is ancestor:
            return True
        current = current.parentWidget()
    return False


def test_keyboard_focus_matrix_covers_every_approved_area() -> None:
    assert keyboard_focus_areas() == EXPECTED_AREAS
    assert len(KEYBOARD_FOCUS_MATRIX) == len(EXPECTED_AREAS)
    assert len(keyboard_focus_test_nodes()) == len(set(keyboard_focus_test_nodes()))


def test_keyboard_focus_matrix_references_existing_test_files() -> None:
    root = Path(__file__).resolve().parents[2]
    missing = {
        node.split("::", maxsplit=1)[0]
        for node in keyboard_focus_test_nodes()
        if not (root / node.split("::", maxsplit=1)[0]).is_file()
    }
    assert not missing


def test_enter_starts_guide_from_welcome(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "welcome-enter.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    assert dialog.welcome_overlay.start_button.hasFocus()
    QTest.keyClick(dialog.welcome_overlay.start_button, Qt.Key.Key_Return)
    qapp.processEvents()

    assert not dialog.welcome_overlay.isVisible()
    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.next_button.hasFocus()


def test_welcome_tab_navigation_stays_inside_overlay(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "welcome-tab.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    for modifiers in (
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ShiftModifier,
    ):
        QTest.keyClick(
            dialog.welcome_overlay.start_button,
            Qt.Key.Key_Tab,
            modifiers,
        )
        qapp.processEvents()
        assert _is_descendant(qapp.focusWidget(), dialog.welcome_overlay)


def test_enter_and_space_navigate_tour(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "tour-navigation.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)

    initial_index = dialog.onboarding.state.current_index
    QTest.keyClick(dialog.tour_overlay.next_button, Qt.Key.Key_Return)
    qapp.processEvents()
    assert dialog.onboarding.state.current_index == initial_index + 1

    dialog.tour_overlay.previous_button.setFocus()
    QTest.keyClick(dialog.tour_overlay.previous_button, Qt.Key.Key_Space)
    qapp.processEvents()
    assert dialog.onboarding.state.current_index == initial_index


def test_tour_tab_navigation_stays_inside_card(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "tour-tab.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)

    for _index in range(6):
        focus = qapp.focusWidget()
        assert focus is not None
        QTest.keyClick(focus, Qt.Key.Key_Tab)
        qapp.processEvents()
        assert _is_descendant(qapp.focusWidget(), dialog.tour_overlay.card)

    focus = qapp.focusWidget()
    assert focus is not None
    QTest.keyClick(
        focus,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.ShiftModifier,
    )
    qapp.processEvents()
    assert _is_descendant(qapp.focusWidget(), dialog.tour_overlay.card)


def test_space_activates_try_it_and_focuses_target(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "try-it.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)
    dialog.onboarding.go_to(3)
    qapp.processEvents()

    assert dialog.tour_overlay.try_button.isVisible()
    dialog.tour_overlay.try_button.setFocus()
    QTest.keyClick(dialog.tour_overlay.try_button, Qt.Key.Key_Space)
    qapp.processEvents()

    assert not dialog.tour_overlay.isVisible()
    assert dialog.scene_name_edit.hasFocus()


def test_keyboard_identity_entry_is_not_interrupted(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "identity.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)
    dialog.onboarding.go_to(3)
    qapp.processEvents()
    QTest.keyClick(dialog.tour_overlay.try_button, Qt.Key.Key_Space)
    qapp.processEvents()

    QTest.keyClicks(dialog.scene_name_edit, "Arrival at Xorix")
    assert not dialog.tour_overlay.isVisible()
    QTest.keyClick(dialog.scene_name_edit, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert dialog.heading_edit.hasFocus()

    QTest.keyClicks(dialog.heading_edit, "EXT. XORIX ORBIT - DAY")
    assert dialog.heading_edit.text() == "EXT. XORIX ORBIT - DAY"
    assert not dialog.tour_overlay.isVisible()
    QTest.keyClick(dialog.heading_edit, Qt.Key.Key_Tab)
    qapp.processEvents()

    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.next_button.isEnabled()
    assert dialog.tour_overlay.next_button.hasFocus()


def test_skipping_welcome_releases_focus_to_editor(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "skip-focus.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    dialog.welcome_overlay.skip_button.setFocus()
    QTest.keyClick(dialog.welcome_overlay.skip_button, Qt.Key.Key_Space)
    qapp.processEvents()
    assert not dialog.welcome_overlay.isVisible()

    dialog.scene_name_edit.setFocus()
    qapp.processEvents()
    assert dialog.scene_name_edit.hasFocus()


def test_escape_closes_scene_editor_without_focus_trap(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "escape.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    QTest.keyClick(dialog.welcome_overlay.start_button, Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not dialog.isVisible()
