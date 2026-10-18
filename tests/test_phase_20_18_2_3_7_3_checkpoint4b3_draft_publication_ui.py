"""Checkpoint 4B.3: publication refuses unknown authority and formats Shot details."""

from PySide6.QtWidgets import QTableWidgetItem

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def test_publication_blocks_without_verified_scope(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._publish_draft()
    assert "BLOCKED" in workspace.draft_status.text()
    assert not (tmp_path / ".vscs" / "episode_assembly").exists()
    assert not workspace.complete_button.isEnabled()


def test_blocker_details_use_actual_line_breaks(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.coverage_table.insertRow(0)
    workspace.coverage_table.setItem(0, 0, QTableWidgetItem("SHT-001"))
    workspace._row_blockers = [("First blocker", "Second blocker")]
    workspace.coverage_table.setCurrentCell(0, 0)
    workspace._show_shot_blockers()
    assert workspace.shot_blockers.toPlainText() == "First blocker\nSecond blocker"


def test_frame_range_requires_staged_media(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._store_frame_range()
    assert workspace.draft_status.text().startswith("BLOCKED:")
    assert workspace._draft_frames == {}


def test_scope_callback_without_valid_evidence_keeps_publish_disabled(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(
        lambda: tmp_path,
        verified_assembly_scope=lambda _episode_id, _shot_ids: None,
    )
    qtbot.addWidget(workspace)
    assert not workspace.publish_draft_button.isEnabled()
    workspace._publish_draft()
    assert "BLOCKED" in workspace.draft_status.text()
    assert not (tmp_path / ".vscs" / "episode_assembly").exists()
