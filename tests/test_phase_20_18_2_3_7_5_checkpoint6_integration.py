"""Phase 20.18.2.3.7.5 final integration acceptance: read-only governance.

The tests exercise the shared UI invalidation gates and immutable application
contracts. Final operator validation must still use the isolated project.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from vscs.application.assembly_contracts import (
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyTimelineRevision,
    ShotSelection,
)
from vscs.application.episode_assembly_boundaries import boundary_pair
from vscs.application.episode_assembly_playback import map_timeline_frame
from vscs.application.episode_assembly_preview import AssemblyPreviewPlan, PreviewSegment
from vscs.application.episode_assembly_revision_comparison import compare_assembly_revisions
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _revisions():
    scope = AssemblyScope("PROD", AssemblyScopeKind.EPISODE, "EP-001", "PLAN-1", "a" * 64)
    source = (
        ShotSelection("SCN-001", "SHT-001", "GM-1", "1", "b" * 64, "APP-1",
                      0, 48, 0, "approved"),
        ShotSelection("SCN-001", "SHT-002", "GM-2", "1", "c" * 64, "APP-2",
                      0, 144, 1, "approved"),
    )
    first = AssemblyTimelineRevision("ASM-EP-001", "REV-001", scope, source, 24, 1)
    second = replace(
        first,
        revision_id="REV-002-ACCEPTANCE",
        predecessor_revision="REV-001",
        selections=(replace(source[0], source_out_frame=24), source[1]),
    )
    return first, second


def _preview(revision):
    start = 0
    segments = []
    for shot in revision.selections:
        segments.append(
            PreviewSegment(
                shot.shot_id, shot.generated_media_id, f"{shot.shot_id}.mp4",
                shot.source_in_frame, shot.source_out_frame, Fraction(24),
                start, start + shot.frame_count,
            )
        )
        start += shot.frame_count
    return AssemblyPreviewPlan(
        revision.assembly_id, revision.revision_id,
        revision.fingerprint, tuple(segments), (), Fraction(24)
    )


def test_checkpoint6_integrated_immutable_comparison_timeline_and_boundary():
    a, b = _revisions()
    fingerprints = a.fingerprint, b.fingerprint
    comparison = compare_assembly_revisions(a, b)
    preview = _preview(b)
    assert [item.change for item in comparison.differences] == ["RANGE", "UNCHANGED"]
    assert comparison.frame_delta == -24
    assert preview.ready and preview.total_frames == 168
    assert map_timeline_frame(preview, 24).segment.shot_id == "SHT-002"
    boundary = boundary_pair(preview, 0)
    assert (boundary.outgoing_frame, boundary.incoming_frame) == (23, 0)
    assert (a.fingerprint, b.fingerprint) == fingerprints
    assert a.selections[0].source_out_frame == 48


def test_checkpoint6_governance_rejects_unverified_media_for_review():
    _, revision = _revisions()
    preview = replace(_preview(revision), blockers=("Unverified approval evidence",))
    with pytest.raises(ValueError, match="verified"):
        map_timeline_frame(preview, 0)
    with pytest.raises(ValueError, match="Verify"):
        boundary_pair(preview, 0)
    assert preview.ready is False


def test_checkpoint6_ui_invalidation_clears_all_review_tools(qtbot, tmp_path):
    widget = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(widget)
    _, revision = _revisions()
    widget._playback_plan = _preview(revision)
    widget._playback_project = tmp_path
    widget._update_playback_controls()
    widget.audio_inspect_button.setEnabled(True)
    widget.boundary_selector.addItem("SHT-001 → SHT-002", 0)
    widget.boundary_inspect.setEnabled(True)
    assert widget.playback_play.isEnabled()
    widget._invalidate()
    assert widget._playback_plan is None
    assert not widget.playback_play.isEnabled()
    assert not widget.boundary_inspect.isEnabled()
    assert not widget.audio_inspect_button.isEnabled()
    assert widget.audio_table.rowCount() == 0
    assert not widget.complete_button.isEnabled()


def test_checkpoint6_assembly_comparison_does_not_authorize_completion(qtbot, tmp_path):
    widget = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(widget)
    a, b = _revisions()
    comparison = compare_assembly_revisions(a, b)
    assert comparison.duration_delta == Fraction(-1)
    assert not widget.complete_button.isEnabled()
    assert widget._selected_revision is None
