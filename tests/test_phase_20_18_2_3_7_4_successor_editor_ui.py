"""Checkpoint 3 successor UI must preserve safe preview and operator control."""

from unittest.mock import patch

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
