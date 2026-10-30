"""Verified Shot persistence is read-only and invalidates stale evidence."""

from dataclasses import replace

import pytest

from vscs.application.caps.authoritative_shot_text import (
    ShotTextAuthorityError,
    VerifiedStorySceneScope,
    assert_shot_text_fresh,
    capture_authoritative_shot_text,
)
from vscs.application.shots.models import ProductionShot


class _Reader:
    def __init__(self, shots: tuple[ProductionShot, ...]) -> None:
        self.shots = shots

    def list_shots(self, scene_id: str | None = None) -> tuple[ProductionShot, ...]:
        return tuple(shot for shot in self.shots if scene_id is None or shot.scene_id == scene_id)


def _shot() -> ProductionShot:
    return ProductionShot(
        shot_id="SHT-001",
        scene_id="SCN-001",
        sequence_number=1,
        title="Console",
        description="Diagnostic Console inside Engineering Control Room.",
        subject_asset_ids=("CAP-PRP-001",),
        required_asset_ids=("CAP-LOC-001",),
    )


def _scope() -> VerifiedStorySceneScope:
    return VerifiedStorySceneScope(
        "STORY-001", "approved-digest", ("SCN-001",), "reviewed-scene-map"
    )


def test_current_shot_text_with_explicit_scene_authority():
    reader = _Reader((_shot(),))
    snapshot = capture_authoritative_shot_text(reader, _scope(), "approved-digest")
    assert snapshot.shots[0].text == _shot().description
    assert snapshot.shots[0].bound_asset_ids == ("CAP-PRP-001", "CAP-LOC-001")
    assert assert_shot_text_fresh(snapshot, reader, _scope(), "approved-digest") == snapshot.shots


def test_changed_shot_text_invalidates_snapshot():
    reader = _Reader((_shot(),))
    snapshot = capture_authoritative_shot_text(reader, _scope(), "approved-digest")
    reader.shots = (replace(_shot(), description="Rewritten scene"),)
    with pytest.raises(ShotTextAuthorityError, match="changed"):
        assert_shot_text_fresh(snapshot, reader, _scope(), "approved-digest")


def test_story_fingerprint_change_fails_closed():
    with pytest.raises(ShotTextAuthorityError, match="fingerprint changed"):
        capture_authoritative_shot_text(_Reader((_shot(),)), _scope(), "different")


def test_unscoped_scene_is_not_misrepresented_as_authoritative():
    reader = _Reader((replace(_shot(), scene_id="SCN-999"),))
    with pytest.raises(ShotTextAuthorityError, match="no persisted Shots"):
        capture_authoritative_shot_text(reader, _scope(), "approved-digest")


def test_missing_scene_map_is_rejected():
    with pytest.raises(ShotTextAuthorityError, match="distinct Scene IDs"):
        VerifiedStorySceneScope("STORY-001", "digest", (), "source")
