"""Tests for Phase 16.2a.8.5.3 Beginner Mode persistence."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from vscs.presentation.dialogs.beginner_mode_scene_editor_dialog import (
    BeginnerModeSceneEditorDialog,
)
from vscs.presentation.workflow import BeginnerModeController


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "beginner-mode.ini"), QSettings.Format.IniFormat)


def test_controller_defaults_enabled_and_persists_changes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    first = BeginnerModeController(settings, "test/beginner")

    assert first.enabled

    first.set_enabled(False)
    second = BeginnerModeController(settings, "test/beginner")

    assert not second.enabled


def test_scene_editor_defaults_to_beginner_mode(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = BeginnerModeSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    assert dialog.beginner_mode.enabled
    assert dialog.beginner_mode_checkbox.isChecked()
    assert dialog.workflow_panel.isVisible()
    assert dialog.workflow_checklist.isEnabled()


def test_disabling_beginner_mode_hides_guided_workflow_only(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = BeginnerModeSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()
    dialog.workflow_navigator.navigate("summary")

    dialog.beginner_mode_checkbox.setChecked(False)
    qapp.processEvents()

    assert not dialog.workflow_panel.isVisible()
    assert not dialog.workflow_checklist.isEnabled()
    assert dialog.workflow_checklist.active_step_id is None
    assert dialog.summary_edit.property("workflowGuidedTarget") is False
    assert dialog.documentation_panel.isVisible()
    assert dialog.knowledge_provider.bindings()
    assert dialog.scene_name_edit.placeholderText()


def test_beginner_mode_preference_is_restored_between_sessions(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    first = BeginnerModeSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    first.beginner_mode_checkbox.setChecked(False)

    second = BeginnerModeSceneEditorDialog(settings=settings)
    qtbot.addWidget(second)  # type: ignore[attr-defined]
    second.show()
    qapp.processEvents()

    assert not second.beginner_mode.enabled
    assert not second.beginner_mode_checkbox.isChecked()
    assert not second.workflow_panel.isVisible()


def test_beginner_mode_can_be_reenabled_without_forcing_panel_open(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    settings.setValue(BeginnerModeSceneEditorDialog.BEGINNER_MODE_KEY, False)
    dialog = BeginnerModeSceneEditorDialog(settings=settings)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.workflow_panel.set_collapsed(True)
    dialog.show()
    qapp.processEvents()

    dialog.beginner_mode_checkbox.setChecked(True)
    qapp.processEvents()

    assert dialog.beginner_mode.enabled
    assert dialog.workflow_panel.isVisible()
    assert dialog.workflow_panel.collapsed
    assert dialog.workflow_checklist.isEnabled()
