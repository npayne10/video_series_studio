"""Tests for Phase 16.2a.7 scene dialog layout and workflow."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog

from vscs.application.ssie import Scene
from vscs.presentation.dialogs.workflow_scene_editor_dialog import (
    WorkflowSceneEditorDialog,
)


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(
        str(tmp_path / "scene-editor.ini"),
        QSettings.Format.IniFormat,
    )


def test_new_and_existing_scene_use_clear_action_labels(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    new_dialog = WorkflowSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(new_dialog)  # type: ignore[attr-defined]
    assert new_dialog.save_button.text() == "Create Scene"
    assert new_dialog.save_button.isDefault()

    scene = Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The crew receives an alert.",
        scene_name="The Alert",
    )
    edit_dialog = WorkflowSceneEditorDialog(
        scene,
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(edit_dialog)  # type: ignore[attr-defined]
    assert edit_dialog.save_button.text() == "Save Changes"


def test_workflow_summary_updates_from_scene_controls(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = WorkflowSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.scene_name_edit.setText("Emergence at Xorix")
    dialog.episode_id_edit.setText("EP-003")
    dialog.sequence_spin.setValue(7)
    dialog.duration_spin.setValue(60.0)

    summary = dialog.summary_label.text()
    assert "EP-003" in summary
    assert "Scene 007" in summary
    assert "Emergence at Xorix" in summary
    assert "60 seconds" in summary


def test_save_shortcut_focuses_first_invalid_field(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = WorkflowSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()

    dialog._save_from_shortcut()

    assert dialog.focusWidget() is dialog.scene_name_edit
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_save_shortcut_accepts_valid_scene(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    scene = Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The crew receives an alert.",
        scene_name="The Alert",
    )
    dialog = WorkflowSceneEditorDialog(
        scene,
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.save_button.isEnabled()
    dialog._save_from_shortcut()

    assert dialog.result() == QDialog.DialogCode.Accepted


def test_dialog_geometry_is_restored_between_sessions(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    first = WorkflowSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    first.resize(910, 650)
    first.done(QDialog.DialogCode.Rejected)

    second = WorkflowSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(second)  # type: ignore[attr-defined]

    assert second.size().width() == 910
    assert second.size().height() == 650
    assert second.summary_frame.parent() is second
    assert second.scroll_area.verticalScrollBarPolicy() == (
        Qt.ScrollBarPolicy.ScrollBarAsNeeded
    )
