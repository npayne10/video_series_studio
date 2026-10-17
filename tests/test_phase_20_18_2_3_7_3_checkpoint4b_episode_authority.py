"""Checkpoint 4B: Episode authority and coverage must fail closed."""

from types import SimpleNamespace

from vscs.application.assembly_contracts import AssemblyScopeKind, AssemblyState
from unittest.mock import Mock

import pytest

from vscs.application.episode_shot_set_resolver import (
    initialize_governed_episode_timeline,
    reconcile_episode_coverage,
    resolve_episode_shots,
)


def _authority(*, approved=True):
    episodes = Mock()
    episodes.plan.return_value = SimpleNamespace(production_ready=True)
    scenes = Mock()
    scenes.list_plans.return_value = (
        SimpleNamespace(scene_id="SCN-001"),
        SimpleNamespace(scene_id="SCN-002"),
    )
    scenes.is_production_ready.return_value = True
    shots = Mock()
    shots.list_plans.side_effect = [
        (SimpleNamespace(shot_id="SHT-001"), SimpleNamespace(shot_id="SHT-002")),
        (SimpleNamespace(shot_id="SHT-003"),),
    ]
    shots.is_production_ready.return_value = True
    reviews = Mock()
    reviews.review.return_value = SimpleNamespace(status="approved") if approved else None
    reviews.is_production_ready.return_value = approved
    return resolve_episode_shots("ep-001", episodes, scenes, shots, reviews)


def test_authoritative_shots_follow_scene_and_shot_plan_order():
    result = _authority()
    assert result.eligible
    assert result.required_shot_ids == ("SHT-001", "SHT-002", "SHT-003")


def test_missing_review_blocks_episode_authority():
    result = _authority(approved=False)
    assert not result.eligible
    assert any("Planning Review" in blocker for blocker in result.blockers)


def test_coverage_blocks_missing_extra_and_unapproved_media():
    authority = _authority()
    selections = (
        SimpleNamespace(shot_id="SHT-001", media_state="approved", approval_evidence_ref="QC-1"),
        SimpleNamespace(shot_id="SHT-999", media_state="generated", approval_evidence_ref=None),
    )
    result = reconcile_episode_coverage(authority, selections)
    assert result.missing == ("SHT-002", "SHT-003")
    assert result.extra == ("SHT-999",)
    assert not result.ready
    assert any("approval evidence" in blocker for blocker in result.blockers)


def test_coverage_accepts_order_but_does_not_declare_completion():
    authority = _authority()
    selections = tuple(
        SimpleNamespace(shot_id=shot, media_state="approved", approval_evidence_ref="QC-1")
        for shot in authority.required_shot_ids
    )
    result = reconcile_episode_coverage(authority, selections)
    assert result.ready
    assert result.missing == ()
    assert result.extra == ()


def test_initialization_rejects_unapproved_media_without_writes():
    authority = _authority()
    revision = SimpleNamespace(
        scope=SimpleNamespace(
            scope_kind=AssemblyScopeKind.EPISODE,
            scope_id="EP-001",
        ),
        state=AssemblyState.DRAFT,
        selections=(
            SimpleNamespace(shot_id="SHT-001", media_state="generated", approval_evidence_ref=None),
        ),
    )
    repository = Mock()
    validator = Mock()
    with pytest.raises(ValueError, match="Timeline initialization blocked"):
        initialize_governed_episode_timeline(authority, revision, repository, validator)
    repository.create.assert_not_called()
    validator.validate.assert_not_called()
