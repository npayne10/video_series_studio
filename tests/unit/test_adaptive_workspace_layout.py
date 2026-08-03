"""Tests for Phase 16.2a.8.5.2a adaptive Scene Editor workspace."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QVBoxLayout

from vscs.presentation.dialogs.adaptive_workspace_scene_editor_dialog import (
    AdaptiveWorkspaceSceneEditorDialog,
)


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "adaptive-workspace.ini"), QSettings.Format.IniFormat)


def test_workspace_prioritises_editor_with_collapsed_support_panels(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = AdaptiveWorkspaceSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    assert dialog.workflow_panel.collapsed
    assert dialog.summary_panel.collapsed
    assert not dialog.validation_panel.collapsed
    assert dialog.workspace_splitter.orientation() is Qt.Orientation.Vertical
    assert dialog.editor_splitter.orientation() is Qt.Orientation.Horizontal
    sizes = dialog.workspace_splitter.sizes()
    assert sizes[1] > sizes[0]
    assert sizes[1] > sizes[2]


def test_panels_can_be_expanded_and_collapsed(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = AdaptiveWorkspaceSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    dialog.workflow_panel.toggle_button.click()
    assert not dialog.workflow_panel.collapsed
    assert dialog.workflow_checklist.isVisibleTo(dialog.workflow_panel)

    dialog.workflow_panel.toggle_button.click()
    assert dialog.workflow_panel.collapsed
    assert not dialog.workflow_checklist.isVisible()


def test_actions_remain_outside_resizable_workspace(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = AdaptiveWorkspaceSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    root = dialog.layout()

    assert isinstance(root, QVBoxLayout)
    assert root.indexOf(dialog.workspace_splitter) >= 0
    assert root.indexOf(dialog.buttons) > root.indexOf(dialog.workspace_splitter)


def test_validation_heading_tracks_blocking_issue_count(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = AdaptiveWorkspaceSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert "4 blocking issues" in dialog.validation_panel.title_label.text()

    dialog.scene_name_edit.setText("Arrival at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    dialog.summary_edit.setPlainText("The crew sees Xorix for the first time.")
    dialog._validate()

    assert dialog.validation_panel.title_label.text() == "Validation · 1 blocking issue"


def test_adaptive_state_is_restored_between_sessions(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    first = AdaptiveWorkspaceSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    first.workflow_panel.set_collapsed(False)
    first.summary_panel.set_collapsed(False)
    first.validation_panel.set_collapsed(True)
    first.workspace_splitter.setSizes([160, 520, 110])
    first.editor_splitter.setSizes([700, 250])
    first._save_adaptive_workspace()

    second = AdaptiveWorkspaceSceneEditorDialog(settings=settings)
    qtbot.addWidget(second)  # type: ignore[attr-defined]

    assert not second.workflow_panel.collapsed
    assert not second.summary_panel.collapsed
    assert second.validation_panel.collapsed
    assert second.workspace_splitter.sizes()[0] > 0
    assert second.editor_splitter.sizes()[0] > second.editor_splitter.sizes()[1]


def test_workspace_remains_usable_at_laptop_size(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = AdaptiveWorkspaceSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.resize(1024, 700)
    dialog.show()
    qapp.processEvents()

    assert dialog.workspace_splitter.isVisible()
    assert dialog.editor_splitter.isVisible()
    assert dialog.save_button.isVisible()
    assert dialog.workspace_splitter.sizes()[1] > 300
