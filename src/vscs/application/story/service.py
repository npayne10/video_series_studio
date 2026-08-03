"""Project-backed structured story storage and SSIE planning."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.ssie import RuleBasedScenePlanner, Scene, ScenePlan, SceneTransition

from .containers import (
    ProductionContainerType,
    build_scene_id,
    infer_container_type,
    normalize_container_id,
)


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
        """Load all scenes in stable production-container order."""
        path = self.story_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            scenes = tuple(self._scene_from_dict(item) for item in raw.get("scenes", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise StoryServiceError(f"Unable to load structured story: {exc}") from exc
        return tuple(
            sorted(
                scenes,
                key=lambda item: (
                    item.episode_id,
                    item.sequence_number,
                    item.scene_id,
                ),
            )
        )

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

    def next_sequence_number(self, container_id: str | None = None) -> int:
        """Return the next available scene sequence for one production container."""
        scenes = self.list_scenes()
        if container_id:
            normalized = container_id.strip().upper()
            scenes = tuple(
                scene for scene in scenes if scene.episode_id.strip().upper() == normalized
            )
        return max((scene.sequence_number for scene in scenes), default=0) + 1

    def default_container_id(self) -> str:
        """Return the most recently used production container ID."""
        scenes = self.list_scenes()
        return scenes[-1].episode_id if scenes else ProductionContainerType.EPISODE.default_id

    def default_container_type(self) -> ProductionContainerType:
        """Return the type inferred from the most recently used container."""
        return infer_container_type(self.default_container_id())

    def default_episode_id(self) -> str:
        """Return the legacy episode-compatible default container ID."""
        return self.default_container_id()

    def container_type_for_scene(self, scene: Scene) -> ProductionContainerType:
        """Return the production-container type owning a scene."""
        return infer_container_type(scene.episode_id)

    def generate_container_scene_id(
        self,
        container_type: ProductionContainerType,
        container_id: str,
        sequence_number: int,
    ) -> str:
        """Generate a unique scene ID for any supported production container."""
        normalized = normalize_container_id(container_id, container_type)
        base = build_scene_id(normalized, sequence_number)
        existing = {scene.scene_id for scene in self.list_scenes()}
        if base not in existing:
            return base
        suffix = 2
        while f"{base}-{suffix}" in existing:
            suffix += 1
        return f"{base}-{suffix}"

    def generate_scene_id(self, episode_id: str, sequence_number: int) -> str:
        """Generate a legacy-compatible episode or container scene ID."""
        container_type = infer_container_type(episode_id)
        return self.generate_container_scene_id(
            container_type,
            episode_id,
            sequence_number,
        )

    def _write(self, scenes: tuple[Scene, ...]) -> None:
        path = self.story_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            scenes,
            key=lambda item: (item.episode_id, item.sequence_number, item.scene_id),
        )
        payload = {
            "schema_version": "1.2",
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
        raw["container_type"] = infer_container_type(scene.episode_id).value
        raw["container_id"] = scene.episode_id
        return raw

    @staticmethod
    def _scene_from_dict(raw: dict[str, Any]) -> Scene:
        heading = str(raw["heading"])
        container_id = str(raw.get("container_id", raw.get("episode_id", "EP-001")))
        return Scene(
            scene_id=str(raw["scene_id"]),
            episode_id=container_id,
            sequence_number=int(raw["sequence_number"]),
            heading=heading,
            location_asset_id=str(raw["location_asset_id"]),
            summary=str(raw["summary"]),
            participant_asset_ids=tuple(
                str(value) for value in raw.get("participant_asset_ids", [])
            ),
            dialogue=tuple(str(value) for value in raw.get("dialogue", [])),
            required_asset_ids=tuple(
                str(value) for value in raw.get("required_asset_ids", [])
            ),
            time_of_day=(
                None if raw.get("time_of_day") is None else str(raw["time_of_day"])
            ),
            transition_in=SceneTransition(str(raw.get("transition_in", "cut"))),
            estimated_duration_seconds=(
                None
                if raw.get("estimated_duration_seconds") is None
                else float(raw["estimated_duration_seconds"])
            ),
            scene_name=str(raw.get("scene_name", "")).strip() or heading,
        )
