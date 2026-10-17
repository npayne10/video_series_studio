"""Phase 20.18.2.3.7.2 assembly contract acceptance tests."""

from dataclasses import FrozenInstanceError, replace
from fractions import Fraction

import pytest

from vscs.application.assembly_contracts import (
    AssemblyContractError,
    AssemblyGovernanceValidator,
    AssemblyScope,
    AssemblyScopeKind,
    AssemblyState,
    AssemblyTimelineRevision,
    ShotSelection,
)


def _scope():
    return AssemblyScope("PROD", AssemblyScopeKind.EPISODE, "EP-001", "SET-1", "a" * 64)


def _shot(index=0, state="approved", approval="QC-1"):
    return ShotSelection(
        scene_id="SCN-001",
        shot_id=f"SHT-{index:03}",
        generated_media_id=f"GM-{index:03}",
        media_revision="1",
        file_checksum="b" * 64,
        approval_evidence_ref=approval,
        source_in_frame=5,
        source_out_frame=245,
        sequence_index=index,
        media_state=state,
    )


def _revision(*shots):
    return AssemblyTimelineRevision("ASM-1", "REV-1", _scope(), tuple(shots), 24, 1)


def test_frame_accurate_duration_fingerprint_and_immutability():
    revision = _revision(_shot(0), _shot(1), _shot(2))
    assert revision.total_frames == 720
    assert revision.duration_seconds == Fraction(30)
    assert len(revision.fingerprint) == 64
    assert revision.fingerprint == _revision(_shot(0), _shot(1), _shot(2)).fingerprint
    assert replace(revision, revision_id="REV-2").fingerprint != revision.fingerprint
    with pytest.raises(FrozenInstanceError):
        revision.revision_id = "tampered"


@pytest.mark.parametrize(
    ("start", "end", "index"),
    [(-1, 2, 0), (1, 1, 0), (3, 2, 0), (0, 5, -1)],
)
def test_invalid_frame_bounds_and_indexes_fail_closed(start, end, index):
    with pytest.raises(AssemblyContractError):
        replace(_shot(), source_in_frame=start, source_out_frame=end, sequence_index=index)


def test_missing_media_integrity_or_approval_fails_closed():
    with pytest.raises(AssemblyContractError, match="file_checksum"):
        replace(_shot(), file_checksum="bad")
    with pytest.raises(AssemblyContractError, match="approval evidence"):
        _shot(0, "approved", None)
    with pytest.raises(AssemblyContractError, match="fingerprint"):
        replace(_scope(), story_structure_fingerprint="invalid")


def test_selection_order_and_revision_identity_must_be_valid():
    with pytest.raises(AssemblyContractError, match="indexes"):
        _revision(_shot(0), _shot(0))
    with pytest.raises(AssemblyContractError, match="indexes"):
        _revision(_shot(1), _shot(0))
    with pytest.raises(AssemblyContractError, match="supersede itself"):
        replace(_revision(_shot()), predecessor_revision="REV-1")
    with pytest.raises(AssemblyContractError, match="Frame rate"):
        replace(_revision(_shot()), frame_rate_den=0)


def test_provisional_source_allowed_for_preview_but_not_picture_lock():
    provisional = _revision(_shot(0, "generated", None))
    validator = AssemblyGovernanceValidator()
    assert validator.validate(provisional, final_use=False).allowed
    assert not validator.validate(provisional, final_use=True).allowed
    under_review = replace(provisional, state=AssemblyState.PROVISIONAL_REVIEW)
    result = validator.transition(
        under_review, AssemblyState.PICTURE_LOCKED, human_approval_ref="OPERATOR-QC"
    )
    assert not result.allowed
    assert "not human-approved" in " ".join(result.blockers)


def test_human_approval_and_ordered_transitions_required():
    validator = AssemblyGovernanceValidator()
    revision = _revision(_shot())
    assert validator.transition(revision, AssemblyState.PROVISIONAL_REVIEW).allowed
    assert not validator.transition(revision, AssemblyState.MASTERED).allowed
    review = replace(revision, state=AssemblyState.PROVISIONAL_REVIEW)
    assert not validator.transition(review, AssemblyState.PICTURE_LOCKED).allowed
    assert validator.transition(
        review, AssemblyState.PICTURE_LOCKED, human_approval_ref="OPERATOR-1"
    ).allowed


def test_empty_timeline_cannot_be_locked_or_approved():
    validator = AssemblyGovernanceValidator()
    empty = replace(_revision(), state=AssemblyState.PROVISIONAL_REVIEW)
    assert not validator.transition(
        empty, AssemblyState.PICTURE_LOCKED, human_approval_ref="OPERATOR-1"
    ).allowed


def test_fractional_frame_rate_is_exact():
    revision = replace(_revision(_shot()), frame_rate_num=24000, frame_rate_den=1001)
    assert revision.duration_seconds == Fraction(240 * 1001, 24000)
