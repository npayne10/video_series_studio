"""Tests for Phase 16.2a.8.5.2 guided workflow navigation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from vscs.presentation.dialogs.guided_navigation_scene_editor_dialog import (
    GuidedNavigationSceneEditorDialog,
)


def test_navigator_maps_every_workflow_step_to_a_target(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    expected = {
        "production_type",
        "container_id",
        "scene_identity",
        "location",
        "summary",
        "participants",
        "required_assets",
        "dialogue",
        "production",
        "validation",
    }

    assert {
        step_id for step_id in expected if dialog.workflow_navigator.target(step_id) is not None
    } == expected


def test_checklist_navigation_focuses_target_and_updates_live_vkf(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()

    button = dialog.workflow_checklist.button_for_step("location")
    assert button is not None
    button.click()
    qapp.processEvents()

    assert dialog.location_combo.hasFocus()
    assert dialog.documentation_panel.topic_id == "scene.location"
    assert dialog.location_combo.property("workflowGuidedTarget") is True


def test_repeated_navigation_restores_previous_highlight(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    original_location_style = dialog.location_combo.styleSheet()

    assert dialog.workflow_navigator.navigate("location")
    assert dialog.location_combo.property("workflowGuidedTarget") is True

    assert dialog.workflow_navigator.navigate("summary")

    assert dialog.location_combo.property("workflowGuidedTarget") is False
    assert dialog.location_combo.styleSheet() == original_location_style
    assert dialog.summary_edit.property("workflowGuidedTarget") is True
    assert dialog.documentation_panel.topic_id == "scene.summary"


def test_highlight_can_be_cleared_without_changing_existing_style(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.scene_name_edit.setStyleSheet("padding: 3px;")

    dialog.workflow_navigator.navigate("scene_identity")
    dialog.workflow_navigator.clear_highlight()

    assert dialog.scene_name_edit.property("workflowGuidedTarget") is False
    assert dialog.scene_name_edit.styleSheet() == "padding: 3px;"


def test_validation_step_highlights_feedback_and_routes_guidance(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.workflow_navigator.navigate("validation")

    assert dialog.validation_label.property("workflowGuidedTarget") is True
    assert dialog.documentation_panel.topic_id == "scene.summary"


def test_unknown_step_is_ignored_safely(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    initial_topic = dialog.documentation_panel.topic_id

    assert not dialog.workflow_navigator.navigate("not-a-step")
    assert dialog.documentation_panel.topic_id == initial_topic


def test_checklist_button_supports_keyboard_activation(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = GuidedNavigationSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    button = dialog.workflow_checklist.button_for_step("summary")
    assert button is not None
    button.setFocus()

    QTest.keyClick(button, Qt.Key.Key_Return)
    qapp.processEvents()

    assert dialog.summary_edit.hasFocus()
    assert dialog.documentation_panel.topic_id == "scene.summary"
    assert dialog.workflow_checklist.active_step_id == "summary"
