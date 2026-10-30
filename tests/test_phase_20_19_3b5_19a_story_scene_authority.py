"""Reviewed Story-to-Scene ownership must be explicit, exclusive and fresh."""

from dataclasses import dataclass

import pytest

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.story_scene_authority import StorySceneAuthority


@dataclass(frozen=True)
class _Scene:
    scene_id: str


class _Scenes:
    def __init__(self, ids: tuple[str, ...]) -> None:
        self.ids = ids

    def list_scenes(self) -> tuple[_Scene, ...]:
        return tuple(_Scene(item) for item in self.ids)


def test_persisted_assignment_round_trip(tmp_path):
    scenes = _Scenes(("SCN-001", "SCN-002"))
    ledger = StorySceneAuthority(tmp_path, scenes)
    scope = ledger.assign("STORY-001", "fingerprint", ("SCN-001",))
    assert scope == StorySceneAuthority(tmp_path, scenes).verify("STORY-001", "fingerprint")
    assert scope.scene_ids == ("SCN-001",)


def test_another_story_cannot_claim_same_scene(tmp_path):
    ledger = StorySceneAuthority(tmp_path, _Scenes(("SCN-001",)))
    ledger.assign("STORY-001", "fingerprint", ("SCN-001",))
    with pytest.raises(ShotTextAuthorityError, match="another Story"):
        ledger.assign("STORY-002", "fingerprint", ("SCN-001",))


def test_changed_story_fingerprint_invalidates_scope(tmp_path):
    ledger = StorySceneAuthority(tmp_path, _Scenes(("SCN-001",)))
    ledger.assign("STORY-001", "fingerprint", ("SCN-001",))
    with pytest.raises(ShotTextAuthorityError, match="stale"):
        ledger.verify("STORY-001", "new-fingerprint")


def test_deleted_scene_invalidates_mapping(tmp_path):
    scenes = _Scenes(("SCN-001",))
    ledger = StorySceneAuthority(tmp_path, scenes)
    ledger.assign("STORY-001", "fingerprint", ("SCN-001",))
    scenes.ids = ()
    with pytest.raises(ShotTextAuthorityError, match="deleted Scenes"):
        ledger.verify("STORY-001", "fingerprint")


def test_missing_mapping_fails_closed(tmp_path):
    with pytest.raises(ShotTextAuthorityError, match="No explicitly reviewed"):
        StorySceneAuthority(tmp_path, _Scenes(("SCN-001",))).verify(
            "STORY-001", "fingerprint"
        )
