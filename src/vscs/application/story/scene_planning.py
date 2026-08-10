"""Production-useful scene planning for Phase 19.3.2."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .containers import build_scene_id
from .episode_planning import EpisodePlan, EpisodePlanningService, EpisodePlanStatus


class ScenePlanningError(RuntimeError):
    """Raised when a scene plan cannot be processed safely."""


class ScenePlanStatus(StrEnum):
    """Minimal governance state for downstream shot planning."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ScenePlan:
    """Scene-level production intent required by downstream planners."""

    scene_id: str
    episode_id: str
    sequence_number: int
    title: str
    story_scope: str
    production_objective: str
    target_runtime_seconds: int
    setting_requirement: str
    required_events: tuple[str, ...]
    continuity_in: str = ""
    continuity_out: str = ""
    scene_constraints: tuple[str, ...] = ()
    episode_contract_hash: str = ""
    status: ScenePlanStatus = ScenePlanStatus.DRAFT


class ScenePlanningService:
    """Persist lean scene plans beneath authoritative Ready Episode Plans."""

    FILE_NAME = "scene_plans.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService, episodes: EpisodePlanningService) -> None:
        self.projects = projects
        self.episodes = episodes

    @property
    def planning_file(self) -> Path:
        """Return the active project's Scene Planner file."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_plans(self, *, episode_id: str | None = None) -> tuple[ScenePlan, ...]:
        """Load scene plans in deterministic episode/sequence order."""
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plans = tuple(self._from_dict(item) for item in raw.get("scenes", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ScenePlanningError(f"Unable to load scene plans: {exc}") from exc
        if episode_id is not None:
            normalized_episode = episode_id.strip().upper()
            plans = tuple(plan for plan in plans if plan.episode_id == normalized_episode)
        return tuple(sorted(plans, key=lambda plan: (plan.episode_id, plan.sequence_number, plan.scene_id)))

    def plan(self, scene_id: str) -> ScenePlan | None:
        """Return one scene plan by stable identity."""
        normalized = scene_id.strip().upper()
        return next((plan for plan in self.list_plans() if plan.scene_id == normalized), None)

    def next_sequence_number(self, episode_id: str) -> int:
        """Return the next scene sequence number for an Episode."""
        return max(
            (plan.sequence_number for plan in self.list_plans(episode_id=episode_id)),
            default=0,
        ) + 1

    def allocated_runtime_seconds(self, episode_id: str) -> int:
        """Return total scene runtime allocated within an Episode."""
        return sum(plan.target_runtime_seconds for plan in self.list_plans(episode_id=episode_id))

    def remaining_runtime_seconds(self, episode_id: str) -> int:
        """Return unallocated runtime in the parent Episode, never below zero."""
        episode = self._require_episode(episode_id)
        return max(0, episode.target_runtime_seconds - self.allocated_runtime_seconds(episode_id))

    def effective_constraints(self, scene: ScenePlan) -> tuple[str, ...]:
        """Return inherited Episode constraints followed by scene-specific constraints."""
        episode = self._require_episode(scene.episode_id)
        return self._values((*episode.production_constraints, *scene.scene_constraints))

    def is_upstream_current(self, scene: ScenePlan) -> bool:
        """Return whether a scene still matches its authoritative Episode contract."""
        episode = self.episodes.plan(scene.episode_id)
        return (
            episode is not None
            and episode.status is EpisodePlanStatus.READY
            and scene.episode_contract_hash == self._episode_contract_hash(episode)
        )

    def is_production_ready(self, scene: ScenePlan) -> bool:
        """Return whether Shot Planning may safely consume this scene."""
        return scene.status is ScenePlanStatus.READY and self.is_upstream_current(scene)

    def create(
        self,
        *,
        episode_id: str,
        sequence_number: int,
        title: str,
        story_scope: str,
        production_objective: str,
        target_runtime_seconds: int,
        setting_requirement: str,
        required_events: tuple[str, ...],
        continuity_in: str = "",
        continuity_out: str = "",
        scene_constraints: tuple[str, ...] = (),
    ) -> ScenePlan:
        """Create a Draft scene from one authoritative Ready Episode Plan."""
        episode = self._require_ready_episode(episode_id)
        if sequence_number < 1:
            raise ScenePlanningError("Scene sequence number must be at least 1")
        scene_id = build_scene_id(episode.episode_id, sequence_number)
        if self.plan(scene_id) is not None:
            raise ScenePlanningError(f"Scene plan already exists: {scene_id}")
        runtime = self._runtime(target_runtime_seconds)
        self._validate_runtime_budget(episode, runtime)
        events = self._values(required_events)
        if not events:
            raise ScenePlanningError("At least one required story event is needed for Shot Planning")
        plan = ScenePlan(
            scene_id=scene_id,
            episode_id=episode.episode_id,
            sequence_number=sequence_number,
            title=self._required(title, "Scene title"),
            story_scope=self._required(story_scope, "Story scope"),
            production_objective=self._required(production_objective, "Production objective"),
            target_runtime_seconds=runtime,
            setting_requirement=self._required(setting_requirement, "Setting requirement"),
            required_events=events,
            continuity_in=continuity_in.strip(),
            continuity_out=continuity_out.strip(),
            scene_constraints=self._values(scene_constraints),
            episode_contract_hash=self._episode_contract_hash(episode),
        )
        self._write((*self.list_plans(), plan))
        return plan

    def update(
        self,
        scene_id: str,
        *,
        title: str,
        story_scope: str,
        production_objective: str,
        target_runtime_seconds: int,
        setting_requirement: str,
        required_events: tuple[str, ...],
        continuity_in: str,
        continuity_out: str,
        scene_constraints: tuple[str, ...],
    ) -> ScenePlan:
        """Update an editable Draft and refresh its Episode contract fingerprint."""
        current = self._require_plan(scene_id)
        if current.status is not ScenePlanStatus.DRAFT:
            raise ScenePlanningError("Ready scene plans must return to Draft before editing")
        episode = self._require_ready_episode(current.episode_id)
        runtime = self._runtime(target_runtime_seconds)
        self._validate_runtime_budget(episode, runtime, excluding_scene_id=current.scene_id)
        events = self._values(required_events)
        if not events:
            raise ScenePlanningError("At least one required story event is needed for Shot Planning")
        updated = replace(
            current,
            title=self._required(title, "Scene title"),
            story_scope=self._required(story_scope, "Story scope"),
            production_objective=self._required(production_objective, "Production objective"),
            target_runtime_seconds=runtime,
            setting_requirement=self._required(setting_requirement, "Setting requirement"),
            required_events=events,
            continuity_in=continuity_in.strip(),
            continuity_out=continuity_out.strip(),
            scene_constraints=self._values(scene_constraints),
            episode_contract_hash=self._episode_contract_hash(episode),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, scene_id: str) -> ScenePlan:
        """Make a current complete scene available to Shot Planning."""
        current = self._require_plan(scene_id)
        if current.status is not ScenePlanStatus.DRAFT:
            return current
        episode = self._require_ready_episode(current.episode_id)
        if current.episode_contract_hash != self._episode_contract_hash(episode):
            raise ScenePlanningError(
                "Scene plan is stale because the Episode contract changed; edit and save it before marking Ready"
            )
        self._validate_ready(current)
        updated = replace(current, status=ScenePlanStatus.READY)
        self._replace(updated)
        return updated

    def return_to_draft(self, scene_id: str) -> ScenePlan:
        """Return a Ready scene to editable Draft state, even if its Episode is stale."""
        current = self._require_plan(scene_id)
        updated = replace(current, status=ScenePlanStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, scene_id: str) -> bool:
        """Delete only a Draft scene plan."""
        current = self.plan(scene_id)
        if current is None:
            return False
        if current.status is not ScenePlanStatus.DRAFT:
            raise ScenePlanningError("Ready scene plans must return to Draft before deletion")
        remaining = tuple(plan for plan in self.list_plans() if plan.scene_id != current.scene_id)
        self._write(remaining)
        return True

    def _validate_ready(self, scene: ScenePlan) -> None:
        self._required(scene.story_scope, "Story scope")
        self._required(scene.production_objective, "Production objective")
        self._required(scene.setting_requirement, "Setting requirement")
        if not scene.required_events:
            raise ScenePlanningError("At least one required story event is needed for Shot Planning")
        self._runtime(scene.target_runtime_seconds)

    def _validate_runtime_budget(
        self,
        episode: EpisodePlan,
        proposed_runtime: int,
        *,
        excluding_scene_id: str | None = None,
    ) -> None:
        allocated = sum(
            plan.target_runtime_seconds
            for plan in self.list_plans(episode_id=episode.episode_id)
            if plan.scene_id != excluding_scene_id
        )
        if allocated + proposed_runtime > episode.target_runtime_seconds:
            remaining = max(0, episode.target_runtime_seconds - allocated)
            raise ScenePlanningError(
                "Scene runtime exceeds the Episode budget "
                f"({remaining} seconds remain of {episode.target_runtime_seconds})"
            )

    def _require_ready_episode(self, episode_id: str) -> EpisodePlan:
        episode = self._require_episode(episode_id)
        if episode.status is not EpisodePlanStatus.READY:
            raise ScenePlanningError("Scene Planning requires a Ready Episode Plan")
        return episode

    def _require_episode(self, episode_id: str) -> EpisodePlan:
        episode = self.episodes.plan(episode_id)
        if episode is None:
            raise ScenePlanningError(f"Episode plan not found: {episode_id}")
        return episode

    def _require_plan(self, scene_id: str) -> ScenePlan:
        scene = self.plan(scene_id)
        if scene is None:
            raise ScenePlanningError(f"Scene plan not found: {scene_id}")
        return scene

    def _replace(self, updated: ScenePlan) -> None:
        plans = tuple(
            updated if plan.scene_id == updated.scene_id else plan
            for plan in self.list_plans()
        )
        self._write(plans)

    def _write(self, plans: tuple[ScenePlan, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(plans, key=lambda plan: (plan.episode_id, plan.sequence_number, plan.scene_id))
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "scenes": [self._to_dict(plan) for plan in ordered],
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
            raise ScenePlanningError(f"Unable to save scene plans: {exc}") from exc

    @staticmethod
    def _to_dict(plan: ScenePlan) -> dict[str, Any]:
        raw = asdict(plan)
        raw["status"] = plan.status.value
        raw["required_events"] = list(plan.required_events)
        raw["scene_constraints"] = list(plan.scene_constraints)
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> ScenePlan:
        return ScenePlan(
            scene_id=str(raw["scene_id"]).strip().upper(),
            episode_id=str(raw["episode_id"]).strip().upper(),
            sequence_number=int(raw["sequence_number"]),
            title=str(raw["title"]),
            story_scope=str(raw["story_scope"]),
            production_objective=str(raw["production_objective"]),
            target_runtime_seconds=int(raw["target_runtime_seconds"]),
            setting_requirement=str(raw["setting_requirement"]),
            required_events=tuple(str(value) for value in raw.get("required_events", [])),
            continuity_in=str(raw.get("continuity_in", "")),
            continuity_out=str(raw.get("continuity_out", "")),
            scene_constraints=tuple(str(value) for value in raw.get("scene_constraints", [])),
            episode_contract_hash=str(raw.get("episode_contract_hash", "")),
            status=ScenePlanStatus(str(raw.get("status", ScenePlanStatus.DRAFT.value))),
        )

    @classmethod
    def _episode_contract_hash(cls, episode: EpisodePlan) -> str:
        payload = {
            "episode_id": episode.episode_id,
            "story_id": episode.story_id,
            "sequence_number": episode.sequence_number,
            "title": episode.title,
            "story_scope": episode.story_scope,
            "production_objective": episode.production_objective,
            "target_runtime_seconds": episode.target_runtime_seconds,
            "continuity_in": episode.continuity_in,
            "continuity_out": episode.continuity_out,
            "production_constraints": list(episode.production_constraints),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ScenePlanningError(f"{label} is required")
        return normalized

    @staticmethod
    def _runtime(value: int) -> int:
        if value <= 0:
            raise ScenePlanningError("Target runtime must be greater than zero")
        return value

    @staticmethod
    def _values(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
