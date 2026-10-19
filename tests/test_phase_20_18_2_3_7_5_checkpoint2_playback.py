"""Phase 3.7.5 Checkpoint 2 — verified non-destructive playback routing."""

from fractions import Fraction

import pytest

from vscs.application.episode_assembly_playback import map_timeline_frame
from vscs.application.episode_assembly_preview import AssemblyPreviewPlan, PreviewSegment
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _plan(ready=True):
    first = PreviewSegment("SHT-001", "GM-1", "a.mp4", 0, 24, Fraction(24), 0, 24)
    second = PreviewSegment("SHT-002", "GM-2", "b.mp4", 0, 144, Fraction(24), 24, 168)
    return AssemblyPreviewPlan("ASM-1", "REV-1", "a" * 64, (first, second),
                               () if ready else ("Missing approval",), Fraction(24))


def test_playback_maps_timeline_boundaries_and_seek_positions():
    plan = _plan()
    assert map_timeline_frame(plan, 0).source_ms == 0
    assert map_timeline_frame(plan, 23).segment_index == 0
    assert map_timeline_frame(plan, 24).segment_index == 1
    assert map_timeline_frame(plan, 48).source_ms == 1000
    assert map_timeline_frame(plan, 167).segment_index == 1


def test_playback_blocks_invalid_or_unverified_ranges():
    with pytest.raises(ValueError, match="verified"):
        map_timeline_frame(_plan(False), 0)
    for frame in (-1, 168):
        with pytest.raises(ValueError, match="outside"):
            map_timeline_frame(_plan(), frame)


def test_playback_buttons_fail_closed_until_preview_verified(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    assert not workspace.playback_play.isEnabled()
    assert not workspace.playback_seek.isEnabled()
    workspace._start_playback()
    assert not workspace.complete_button.isEnabled()
    assert workspace.playback_player.mediaStatus() is not None
