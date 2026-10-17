"""Checkpoint 4B.2: staging is a local UI draft, not a governed publication."""

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_draft_media_staging_requires_shot_and_eligible_media(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._stage_selected_media()
    assert workspace.draft_status.text().startswith("BLOCKED:")
    assert not workspace.complete_button.isEnabled()


def test_draft_media_staging_is_cleared_on_authority_change(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._staged_media["SHT-001"] = "GM-001"
    workspace._invalidate()
    assert workspace._staged_media == {}
    assert not workspace.complete_button.isEnabled()


def test_draft_media_staging_never_publishes(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.coverage_table.insertRow(0)
    from PySide6.QtWidgets import QTableWidgetItem

    workspace.coverage_table.setItem(0, 0, QTableWidgetItem("SHT-001"))
    workspace.coverage_table.setCurrentCell(0, 0)
    workspace._draft_candidates["SHT-001"] = ("GM-001",)
    workspace._show_shot_blockers()
    workspace.draft_media_selector.setCurrentIndex(1)
    workspace._stage_selected_media()
    assert workspace._staged_media == {"SHT-001": "GM-001"}
    assert not (tmp_path / ".vscs" / "episode_assembly").exists()
    assert not workspace.complete_button.isEnabled()
