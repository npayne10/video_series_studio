"""Checkpoint 3 successor UI must preserve safe preview and operator control."""

from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_successor_editor_defaults_to_no_publication(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    assert workspace.successor_revision_id.objectName() == "successorRevisionId"
    assert workspace.successor_comparison.objectName() == "successorComparison"
    assert not workspace.successor_publish_button.isEnabled()
    assert not workspace.complete_button.isEnabled()


def test_successor_preview_blocks_without_persisted_predecessor(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.successor_revision_id.setText("REV-002")
    workspace._preview_successor()
    assert "BLOCKED" in workspace.successor_status.text()
    assert not workspace.successor_publish_button.isEnabled()


def test_successor_publish_cannot_run_without_preview(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    with patch(
        "vscs.presentation.widgets.episode_assembly_workspace.JsonAssemblyTimelineRepository"
    ) as repository:
        workspace._publish_successor()
    repository.assert_not_called()
    assert "BLOCKED" in workspace.successor_status.text()


def test_successor_preview_invalidated_when_operator_changes(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._successor_candidate = object()
    workspace._successor_predecessor_fingerprint = "a" * 64
    workspace._successor_operator_evidence = ("operator", "reason")
    workspace.successor_publish_button.setEnabled(True)
    workspace.successor_operator.setText("different operator")
    assert workspace._successor_candidate is None
    assert workspace._successor_operator_evidence is None
    assert not workspace.successor_publish_button.isEnabled()


def test_rejected_confirmation_writes_no_successor_or_decisions(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    candidate = SimpleNamespace(
        fingerprint="a" * 64,
        assembly_id="ASM-1",
        revision_id="REV-002",
        selections=(),
    )
    predecessor = SimpleNamespace(fingerprint="b" * 64, selections=())
    workspace._selected_revision = predecessor
    workspace._successor_candidate = candidate
    workspace._successor_predecessor_fingerprint = predecessor.fingerprint
    workspace._successor_operator_evidence = ("", "")
    with (
        patch.object(workspace, "_build_successor_candidate", return_value=candidate),
        patch(
            "vscs.presentation.widgets.episode_assembly_workspace.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as confirm,
        patch(
            "vscs.presentation.widgets.episode_assembly_workspace.JsonAssemblyTimelineRepository"
        ) as timeline,
        patch(
            "vscs.presentation.widgets.episode_assembly_workspace.JsonReplacementDecisionRepository"
        ) as decisions,
    ):
        workspace._publish_successor()
    confirm.assert_called_once()
    timeline.assert_not_called()
    decisions.assert_not_called()
    assert not workspace.complete_button.isEnabled()
