"""Read-only A/B comparison contract and UI governance regression."""

from dataclasses import replace
from fractions import Fraction

import pytest

from vscs.application.assembly_contracts import (
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyTimelineRevision,
    ShotSelection,
)
from vscs.application.episode_assembly_revision_comparison import compare_assembly_revisions
from vscs.presentation.widgets.episode_assembly_workspace import EpisodeAssemblyWorkspace


def _revision(revision_id="REV-001", end=48, extra=False):
    scope = AssemblyScope("PROD", AssemblyScopeKind.EPISODE, "EP-001", "PLAN-1", "a" * 64)
    selections = [
        ShotSelection("SCN", "SHT-001", "GM-001", "1", "b" * 64, "APP-1", 0, end, 0, "approved"),
        ShotSelection("SCN", "SHT-002", "GM-002", "1", "c" * 64, "APP-2", 0, 144, 1, "approved"),
    ]
    if extra:
        selections.append(
            ShotSelection("SCN", "SHT-003", "GM-003", "1", "d" * 64, "APP-3", 0, 24, 2, "approved")
        )
    return AssemblyTimelineRevision("ASM-EP-001", revision_id, scope, tuple(selections), 24, 1)


def test_comparison_detects_range_duration_and_unchanged_shot():
    result = compare_assembly_revisions(_revision(), _revision("REV-002", 24))
    assert result.frame_delta == -24
    assert result.duration_delta == Fraction(-1)
    assert [x.change for x in result.differences] == ["RANGE", "UNCHANGED"]
    assert result.differences[0].range_a == (0, 48)
    assert result.differences[0].range_b == (0, 24)


def test_comparison_added_removed_media_and_order():
    a = _revision()
    b = _revision("REV-002", extra=True)
    assert compare_assembly_revisions(a, b).differences[2].change == "ADDED"
    assert compare_assembly_revisions(b, a).differences[2].change == "REMOVED"
    first, second = b.selections[:2]
    swapped = replace(
        b,
        selections=(
            replace(second, sequence_index=0),
            replace(first, sequence_index=1),
            b.selections[2],
        ),
    )
    changes = compare_assembly_revisions(a, swapped)
    assert all("ORDER" in entry.change for entry in changes.differences[:2])
    updated = replace(
        b,
        selections=(replace(b.selections[0], generated_media_id="GM-NEW"), *b.selections[1:]),
    )
    assert "MEDIA/EVIDENCE" in compare_assembly_revisions(a, updated).differences[0].change


def test_comparison_rejects_incompatible_or_same_revision():
    a = _revision()
    with pytest.raises(ValueError, match="distinct"):
        compare_assembly_revisions(a, a)
    with pytest.raises(ValueError, match="frame rates"):
        compare_assembly_revisions(a, replace(_revision("REV-002"), frame_rate_num=30))
    other = replace(_revision("REV-002"), assembly_id="OTHER")
    with pytest.raises(ValueError, match="identical assembly"):
        compare_assembly_revisions(a, other)


def test_comparison_ui_starts_read_only_and_fails_closed(qtbot, tmp_path):
    workspace = EpisodeAssemblyWorkspace(lambda: tmp_path)
    qtbot.addWidget(workspace)
    workspace._compare_revisions()
    assert workspace.compare_status.text().startswith("BLOCKED:")
    assert workspace.compare_table.rowCount() == 0
    assert not workspace.complete_button.isEnabled()
