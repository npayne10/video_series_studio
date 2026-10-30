"""Explicit project-local Story-to-Scene mapping, verified against current authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.authoritative_shot_text import (
    ShotTextAuthorityError,
    VerifiedStorySceneScope,
)
from vscs.application.story.service import StoryService

_FILE = "story_scene_authority.json"


@dataclass(frozen=True)
class StorySceneAssignment:
    story_id: str
    story_fingerprint: str
    scene_ids: tuple[str, ...]


class StorySceneAuthority:
    """Separate operator-confirmed ownership; never infer from episode names."""

    def __init__(self, project_root: Path, scenes: StoryService) -> None:
        self.path = project_root / "story" / _FILE
        self.scenes = scenes

    def _read(self) -> dict[str, object]:
        if not self.path.is_file():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("Unsupported authority schema")
            return data
        except (OSError, ValueError) as exc:
            raise ShotTextAuthorityError("Story/Scene authority ledger is invalid") from exc

    def verify(
        self, story_id: str, approved_fingerprint: str
    ) -> VerifiedStorySceneScope:
        data = self._read()
        entries = data.get("assignments", {})
        if not isinstance(entries, dict):
            raise ShotTextAuthorityError("Story/Scene authority assignments invalid")
        record = entries.get(story_id)
        if not isinstance(record, dict):
            raise ShotTextAuthorityError("No explicitly reviewed Story-to-Scene ownership")
        if record.get("story_fingerprint") != approved_fingerprint:
            raise ShotTextAuthorityError("Story-to-Scene authority stale after Story change")
        ids = record.get("scene_ids")
        if not isinstance(ids, list) or not all(isinstance(x, str) for x in ids):
            raise ShotTextAuthorityError("Story-to-Scene list invalid")
        scene_ids = tuple(ids)
        actual = {scene.scene_id for scene in self.scenes.list_scenes()}
        if not set(scene_ids).issubset(actual):
            raise ShotTextAuthorityError("Story-to-Scene mapping references deleted Scenes")
        for other_story, other in entries.items():
            if other_story != story_id and isinstance(other, dict):
                other_ids = other.get("scene_ids", [])
                if isinstance(other_ids, list) and set(scene_ids) & set(other_ids):
                    raise ShotTextAuthorityError("Scenes claimed by multiple Stories")
        return VerifiedStorySceneScope(
            story_id, approved_fingerprint, scene_ids, f"operator-confirmed:{self.path.name}"
        )

    def assign(
        self,
        story_id: str,
        approved_fingerprint: str,
        scene_ids: tuple[str, ...],
    ) -> VerifiedStorySceneScope:
        """Persist only explicitly selected Scene IDs; caller obtains operator consent."""
        if not scene_ids or len(scene_ids) != len(set(scene_ids)):
            raise ShotTextAuthorityError("Select distinct Scenes before assigning ownership")
        existing = self._read()
        entries = existing.get("assignments", {})
        if not isinstance(entries, dict):
            raise ShotTextAuthorityError("Story/Scene authority assignments invalid")
        current = {scene.scene_id for scene in self.scenes.list_scenes()}
        if not set(scene_ids).issubset(current):
            raise ShotTextAuthorityError("Selected Scenes are no longer present")
        for key, value in entries.items():
            if key != story_id and isinstance(value, dict):
                used = value.get("scene_ids", [])
                if isinstance(used, list) and set(scene_ids) & set(used):
                    raise ShotTextAuthorityError("Scene already assigned to another Story")
        updated = dict(entries)
        updated[story_id] = {
            "story_fingerprint": approved_fingerprint,
            "scene_ids": list(scene_ids),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        try:
            temporary.write_text(
                json.dumps({"schema_version": 1, "assignments": updated}, indent=2)
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise ShotTextAuthorityError("Unable to persist Scene ownership") from exc
        return self.verify(story_id, approved_fingerprint)
