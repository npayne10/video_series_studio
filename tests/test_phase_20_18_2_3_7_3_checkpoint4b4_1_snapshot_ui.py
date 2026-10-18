"""Fail-closed operator authorization UI for initial partial Draft planning scope."""

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_snapshot_ui_requires_open_project_and_episode(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._authorize_planning_snapshot()
    assert workspace.draft_status.text().startswith("BLOCKED:")
    assert not workspace.publish_draft_button.isEnabled()
    assert not (tmp_path / ".vscs" / "episode_assembly").exists()


def test_snapshot_ui_remains_unpublished_without_production_identity(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.snapshot_operator.setText("operator")
    workspace._authorize_planning_snapshot()
    assert not workspace.publish_draft_button.isEnabled()
    assert not (tmp_path / ".vscs" / "episode_assembly").exists()
