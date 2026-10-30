"""Read-only Shot text snapshots gated by explicit Story/Scene authority and freshness."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Protocol

from vscs.application.caps.shot_spatial_evidence import ShotSpatialSource
from vscs.application.shots.models import ProductionShot


class ShotTextAuthorityError(ValueError):
    """Shot evidence has missing or stale project authority."""


class ShotTextReader(Protocol):
    def list_shots(self, scene_id: str | None = None) -> tuple[ProductionShot, ...]: ...


@dataclass(frozen=True)
class VerifiedStorySceneScope:
    story_id: str
    story_fingerprint: str
    scene_ids: tuple[str, ...]
    source: str

    def __post_init__(self) -> None:
        if not self.story_id or not self.story_fingerprint or not self.source:
            raise ShotTextAuthorityError("Story scope needs explicit provenance and fingerprint")
        if not self.scene_ids or len(set(self.scene_ids)) != len(self.scene_ids):
            raise ShotTextAuthorityError("Verified Story scope needs distinct Scene IDs")


@dataclass(frozen=True)
class AuthoritativeShotSnapshot:
    story_id: str
    story_fingerprint: str
    scope_source: str
    shot_fingerprint: str
    shots: tuple[ShotSpatialSource, ...]


def _shot_payload(shot: ProductionShot) -> dict[str, object]:
    return {
        "shot_id": shot.shot_id,
        "scene_id": shot.scene_id,
        "description": shot.description,
        "blocking_notes": shot.blocking_notes,
        "continuity_notes": shot.continuity_notes,
        "subject_asset_ids": list(shot.subject_asset_ids),
        "required_asset_ids": list(shot.required_asset_ids),
    }


def _current(
    reader: ShotTextReader,
    scope: VerifiedStorySceneScope,
    current_story_fingerprint: str,
) -> AuthoritativeShotSnapshot:
    if current_story_fingerprint != scope.story_fingerprint:
        raise ShotTextAuthorityError("Approved Story fingerprint changed; Shot evidence is stale")
    allowed = set(scope.scene_ids)
    selected = tuple(shot for shot in reader.list_shots() if shot.scene_id in allowed)
    if not selected:
        raise ShotTextAuthorityError("Verified Story scenes have no persisted Shots")
    if len({shot.shot_id for shot in selected}) != len(selected):
        raise ShotTextAuthorityError("Duplicate Shot IDs prevent authoritative evidence")
    payload = [_shot_payload(shot) for shot in sorted(selected, key=lambda item: item.shot_id)]
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    sources = tuple(
        ShotSpatialSource(
            shot_id=shot.shot_id,
            story_id=scope.story_id,
            text=shot.description,
            bound_asset_ids=tuple(
                dict.fromkeys((*shot.subject_asset_ids, *shot.required_asset_ids))
            ),
        )
        for shot in selected
    )
    return AuthoritativeShotSnapshot(
        scope.story_id, scope.story_fingerprint, scope.source, fingerprint, sources
    )


def capture_authoritative_shot_text(
    reader: ShotTextReader,
    scope: VerifiedStorySceneScope,
    current_story_fingerprint: str,
) -> AuthoritativeShotSnapshot:
    """Capture a read-only current snapshot after verified Story authority."""
    return _current(reader, scope, current_story_fingerprint)


def assert_shot_text_fresh(
    snapshot: AuthoritativeShotSnapshot,
    reader: ShotTextReader,
    scope: VerifiedStorySceneScope,
    current_story_fingerprint: str,
) -> tuple[ShotSpatialSource, ...]:
    """Refuse an outdated Shot or Story; never substitute stale cached evidence."""
    current = _current(reader, scope, current_story_fingerprint)
    if current != snapshot:
        raise ShotTextAuthorityError("Shot evidence or Story/Scene scope changed; review again")
    return current.shots
