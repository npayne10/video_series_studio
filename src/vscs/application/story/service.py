"""Project-backed structured story storage and SSIE planning."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.ssie import RuleBasedScenePlanner, Scene, ScenePlan, SceneTransition


class StoryServiceError(RuntimeError):
    """Raised when structured story data cannot be loaded or saved."""


class StoryService:
    """Persist structured scenes and generate deterministic SSIE plans."""

    FILE_NAME = "scenes.json"

    def __init__(
        self,
        projects: ProjectService,
        planner: RuleBasedScenePlanner | None = None,
    ) -> None:
        self.projects = projects
        self.planner = planner or RuleBasedScenePlanner()
        self._plans: dict[str, ScenePlan] = {}

    @property
    def story_file(self) -> Path:
        """Return the active project's structured story file."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.FILE_NAME

    def list_scenes(self) -> tuple[Scene, ...]:
        """Load all scenes in sequence order."""
        path = self.story_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            scenes = tuple(self._scene_from_dict(item) for item in raw.get("scenes", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise StoryServiceError(f"Unable to load structured story: {exc}") from exc
        return tuple(sorted(scenes, key=lambda item: (item.sequence_number, item.scene_id)))

    def save_scene(self, scene: Scene) -> Scene:
        """Create or replace one structured scene."""
        scenes = {item.scene_id: item for item in self.list_scenes()}
        scenes[scene.scene_id] = scene
        self._write(tuple(scenes.values()))
        self._plans.pop(scene.scene_id, None)
        return scene

    def delete_scene(self, scene_id: str) -> bool:
        """Delete one scene by identity."""
        scenes = {item.scene_id: item for item in self.list_scenes()}
        removed = scenes.pop(scene_id, None)
        if removed is None:
            return False
        self._write(tuple(scenes.values()))
        self._plans.pop(scene_id, None)
        return True

    def scene(self, scene_id: str) -> Scene | None:
        """Return one scene by identity."""
        return next((item for item in self.list_scenes() if item.scene_id == scene_id), None)

    def plan_scene(self, scene_id: str) -> ScenePlan:
        """Generate and cache the SSIE plan for one scene."""
        scene = self.scene(scene_id)
        if scene is None:
            raise StoryServiceError(f"Scene not found: {scene_id}")
        plan = self.planner.plan_scene(scene)
        self._plans[scene_id] = plan
        return plan

    def plan(self, scene_id: str) -> ScenePlan | None:
        """Return the current in-memory SSIE plan for one scene."""
        return self._plans.get(scene_id)

    def _write(self, scenes: tuple[Scene, ...]) -> None:
        path = self.story_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(scenes, key=lambda item: (item.sequence_number, item.scene_id))
        payload = {
            "schema_version": "1.0",
            "scenes": [self._scene_to_dict(scene) for scene in ordered],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StoryServiceError(f"Unable to save structured story: {exc}") from exc

    @staticmethod
    def _scene_to_dict(scene: Scene) -> dict[str, Any]:
        raw = asdict(scene)
        raw["transition_in"] = scene.transition_in.value
        return raw

    @staticmethod
    def _scene_from_dict(raw: dict[str, Any]) -> Scene:
        return Scene(
            scene_id=str(raw["scene_id"]),
            episode_id=str(raw["episode_id"]),
            sequence_number=int(raw["sequence_number"]),
            heading=str(raw["heading"]),
            location_asset_id=str(raw["location_asset_id"]),
            summary=str(raw["summary"]),
            participant_asset_ids=tuple(str(value) for value in raw.get("participant_asset_ids", [])),
            dialogue=tuple(str(value) for value in raw.get("dialogue", [])),
            required_asset_ids=tuple(str(value) for value in raw.get("required_asset_ids", [])),
            time_of_day=(None if raw.get("time_of_day") is None else str(raw["time_of_day"])),
            transition_in=SceneTransition(str(raw.get("transition_in", "cut"))),
            estimated_duration_seconds=(
                None
                if raw.get("estimated_duration_seconds") is None
                else float(raw["estimated_duration_seconds"])
            ),
        )
