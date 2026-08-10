"""Tests for Phase 16.2a.8.5.1 workflow progress checklist."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QApplication

from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.beginner_workflow_scene_editor_dialog import (
    BeginnerWorkflowSceneEditorDialog,
)
from vscs.presentation.workflow import SCENE_WORKFLOW_STEPS


def _location() -> Asset:
    now = datetime.now(UTC)
    return Asset(
        id=1,
        asset_id="LOC-XORIX-ORBIT",
        name="Xorix Orbit",
        category=AssetCategory.LOCATION,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
        created_at=now,
        updated_at=now,
    )


def test_scene_workflow_model_has_stable_order_and_topics() -> None:
    assert tuple(step.step_id for step in SCENE_WORKFLOW_STEPS) == (
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
    )
    assert all(step.topic_id.startswith("scene.") for step in SCENE_WORKFLOW_STEPS)


def test_checklist_shows_live_progress_and_next_recommendation(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = BeginnerWorkflowSceneEditorDialog(location_assets=(_location(),))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.workflow_checklist.progress_bar.maximum() == 100
    assert dialog.workflow_checklist.progress_bar.value() < 100
    assert "Name and identify" in (
        dialog.workflow_checklist.button_for_step("scene_identity").text()
    )
    assert "Enter a short scene name" in (dialog.workflow_checklist.next_step_label.text())

    initial_value = dialog.workflow_checklist.progress_bar.value()
    dialog.scene_name_edit.setText("Arrival at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    qapp.processEvents()

    assert dialog.workflow_checklist.progress_bar.value() > initial_value
    assert "Select the canonical location" in (dialog.workflow_checklist.next_step_label.text())


def test_completed_required_scene_reaches_full_progress(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = BeginnerWorkflowSceneEditorDialog(location_assets=(_location(),))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.scene_name_edit.setText("Arrival at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    location_index = dialog.location_combo.findData("LOC-XORIX-ORBIT")
    dialog.location_combo.setCurrentIndex(location_index)
    dialog.summary_edit.setPlainText(
        "The ship enters orbit and the crew sees Xorix for the first time."
    )
    qapp.processEvents()

    assert dialog.save_button.isEnabled()
    assert dialog.workflow_checklist.progress_bar.value() == 100
    assert dialog.workflow_checklist.next_step_label.text() == ("Scene complete. Ready to save.")
    assert dialog.workflow_checklist.button_for_step("validation").text().startswith("✓")


def test_clicking_checklist_step_routes_focus_and_live_help(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = BeginnerWorkflowSceneEditorDialog(location_assets=(_location(),))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()

    button = dialog.workflow_checklist.button_for_step("location")
    assert button is not None
    button.click()
    qapp.processEvents()

    assert dialog.location_combo.hasFocus()
    assert dialog.documentation_panel.topic_id == "scene.location"
