"""Checkpoint 4B.5: automatic discovery, inspection and staging summary."""

from types import SimpleNamespace
from unittest.mock import patch

from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _revision(revision_id: str):
    selection = SimpleNamespace(
        shot_id="EP-001-SCN-001-SHT-001",
        generated_media_id="GM-1",
        media_state="approved",
        approval_evidence_ref="QC-1",
    )
    return SimpleNamespace(
        assembly_id="ASM-EP-001",
        revision_id=revision_id,
        scope=SimpleNamespace(scope_id="EP-001"),
        selections=(selection,),
    )


def test_newly_published_revision_auto_selected_and_inspected(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    revision = _revision("REV-001")
    with patch(
        "vscs.presentation.widgets.episode_assembly_workspace.JsonAssemblyTimelineRepository"
    ) as repository_class:
        repository = repository_class.return_value
        repository.list_revisions.return_value = (revision,)
        repository.get.return_value = revision
        workspace.discover_revisions(select_identity=("ASM-EP-001", "REV-001"))
    assert tuple(workspace.persisted_revisions.currentData()) == ("ASM-EP-001", "REV-001")
    assert workspace.assembly_id.text() == "ASM-EP-001"
    assert workspace.revision_id.text() == "REV-001"
    assert workspace.table.rowCount() == 1
    assert workspace.table.item(0, 1).text() == "GM-1"
    assert not workspace.complete_button.isEnabled()


def test_discovery_without_revisions_remains_fail_closed(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace.discover_revisions(select_identity=("ASM-EP-001", "REV-001"))
    assert "No persisted timeline revisions" in workspace.status.text()
    assert not workspace.complete_button.isEnabled()


def test_staged_media_summary_tracks_media_and_frame_ranges(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._staged_media.update({"SHT-002": "GM-2", "SHT-001": "GM-1"})
    workspace._draft_frames["SHT-002"] = (0, 144)
    workspace._update_staged_summary()
    assert workspace.staged_summary.rowCount() == 2
    assert workspace.staged_summary.item(0, 0).text() == "SHT-001"
    assert workspace.staged_summary.item(0, 3).text() == "Needs source range"
    assert workspace.staged_summary.item(1, 2).text() == "[0, 144)"
    workspace._invalidate()
    assert workspace.staged_summary.rowCount() == 0
    assert not workspace.complete_button.isEnabled()
