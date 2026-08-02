"""Tests for Phase 16.2a.1 scene identity and general details UX."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.scene_editor_dialog import SceneEditorDialog


def test_new_scene_generates_read_only_identity(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog(
        default_episode_id="EP-004",
        suggested_sequence=7,
        scene_id_factory=lambda episode, sequence: f"{episode}-SCN-{sequence:03d}",
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.scene_id_edit.text() == "EP-004-SCN-007"
    assert dialog.scene_id_edit.isReadOnly()

    dialog.sequence_spin.setValue(8)

    assert dialog.scene_id_edit.text() == "EP-004-SCN-008"


def test_save_remains_disabled_until_required_fields_are_complete(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert not dialog.save_button.isEnabled()
    assert "scene name" in dialog.validation_label.text()

    dialog.scene_name_edit.setText("Emergence at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    dialog.location_edit.setText("LOC-XORIX-ORBIT")
    dialog.summary_edit.setPlainText("The Iron Horizon arrives above Xorix.")

    assert dialog.save_button.isEnabled()
    assert dialog.validation_label.text() == ""


def test_dialog_returns_separate_scene_name_and_heading(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog(default_episode_id="EP-002", suggested_sequence=3)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.scene_name_edit.setText("First Sight of Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    dialog.location_edit.setText("LOC-XORIX-ORBIT")
    dialog.summary_edit.setPlainText("The crew sees Xorix for the first time.")

    scene = dialog.scene()

    assert scene.scene_name == "First Sight of Xorix"
    assert scene.heading == "EXT. XORIX ORBIT - DAY"
    assert scene.scene_id == "EP-002-SCN-003"


def test_editing_preserves_existing_scene_identity(
    qtbot: object,
    qapp: QApplication,
) -> None:
    scene = Scene(
        scene_id="EP-001-SCN-004",
        episode_id="EP-001",
        sequence_number=4,
        heading="INT. BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The bridge crew receives an alert.",
        scene_name="The Alert",
    )
    dialog = SceneEditorDialog(scene)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.sequence_spin.setValue(9)
    dialog.episode_id_edit.setText("EP-003")

    assert dialog.scene_id_edit.text() == "EP-001-SCN-004"
    assert dialog.scene_name_edit.text() == "The Alert"
