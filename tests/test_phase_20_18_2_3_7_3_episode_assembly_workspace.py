"""Checkpoint 3: Episode Assembly workspace remains fail closed."""

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_episode_assembly_no_project_blocks(qtbot):
    workspace = EpisodeAssemblyWorkspace(lambda: None)
    qtbot.addWidget(workspace)
    workspace.assembly_id.setText("ASM-1")
    workspace.revision_id.setText("REV-1")
    workspace.refresh()
    assert "Open a VSCS project" in workspace.status.text()
    assert not workspace.complete_button.isEnabled()


def test_episode_assembly_missing_revision_blocks(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.assembly_id.setText("ASM-1")
    workspace.revision_id.setText("REV-1")
    workspace.refresh()
    assert "not found" in workspace.status.text()
    assert workspace.table.rowCount() == 0
    assert not workspace.complete_button.isEnabled()


def test_episode_assembly_fields_invalidate(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.assembly_id.setText("ASM-1")
    workspace.revision_id.setText("REV-1")
    workspace.refresh()
    workspace.revision_id.setText("REV-2")
    assert workspace.table.rowCount() == 0
    assert not workspace.complete_button.isEnabled()


def test_episode_assembly_stages_are_not_operational(qtbot):
    workspace = EpisodeAssemblyWorkspace(lambda: None)
    qtbot.addWidget(workspace)
    assert "Picture Lock" in workspace.stages.text()
    assert "Mastering" in workspace.stages.text()
    assert not workspace.complete_button.isEnabled()
