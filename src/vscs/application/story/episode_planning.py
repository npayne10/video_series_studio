"""Production-useful episode planning for Phase 19.3.1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .lifecycle import StoryLifecycleService


class EpisodePlanningError(RuntimeError):
    """Raised when an episode plan cannot be processed safely."""


class EpisodePlanStatus(StrEnum):
    """Minimal governance state for downstream planning consumption."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class EpisodePlan:
    """Episode-level production intent required by downstream planners."""

    episode_id: str
    story_id: str
    sequence_number: int
    title: str
    story_scope: str
    production_objective: str
    target_runtime_seconds: int
    continuity_in: str = ""
    continuity_out: str = ""
    production_constraints: tuple[str, ...] = ()
    status: EpisodePlanStatus = EpisodePlanStatus.DRAFT

    @property
    def production_ready(self) -> bool:
        """Return whether the plan may be consumed by downstream planning."""
        return self.status is EpisodePlanStatus.READY


class EpisodePlanningService:
    """Persist lean episode plans beneath the active project Story workspace."""

    FILE_NAME = "episode_plans.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService, stories: StoryLifecycleService) -> None:
        self.projects = projects
        self.stories = stories

    @property
    def planning_file(self) -> Path:
        """Return the active project's Episode Planner file."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "planning" / self.FILE_NAME

    def list_plans(self, *, story_id: str | None = None) -> tuple[EpisodePlan, ...]:
        """Load plans in deterministic episode sequence order."""
        path = self.planning_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plans = tuple(self._from_dict(item) for item in raw.get("episodes", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise EpisodePlanningError(f"Unable to load episode plans: {exc}") from exc
        if story_id is not None:
            plans = tuple(plan for plan in plans if plan.story_id == story_id)
        return tuple(sorted(plans, key=lambda plan: (plan.sequence_number, plan.episode_id)))

    def plan(self, episode_id: str) -> EpisodePlan | None:
        """Return one episode plan by stable identity."""
        normalized = episode_id.strip().upper()
        return next((plan for plan in self.list_plans() if plan.episode_id == normalized), None)

    def next_sequence_number(self, story_id: str) -> int:
        """Return the next episode sequence for one Story."""
        return max((plan.sequence_number for plan in self.list_plans(story_id=story_id)), default=0) + 1

    def create(
        self,
        *,
        story_id: str,
        sequence_number: int,
        title: str,
        story_scope: str,
        production_objective: str,
        target_runtime_seconds: int,
        continuity_in: str = "",
        continuity_out: str = "",
        production_constraints: tuple[str, ...] = (),
    ) -> EpisodePlan:
        """Create a draft episode plan linked to an existing Story."""
        self._require_story(story_id)
        if sequence_number < 1:
            raise EpisodePlanningError("Episode sequence number must be at least 1")
        episode_id = f"EP-{sequence_number:03d}"
        if self.plan(episode_id) is not None:
            raise EpisodePlanningError(f"Episode plan already exists: {episode_id}")
        plan = EpisodePlan(
            episode_id=episode_id,
            story_id=story_id,
            sequence_number=sequence_number,
            title=self._required(title, "Episode title"),
            story_scope=self._required(story_scope, "Story scope"),
            production_objective=self._required(production_objective, "Production objective"),
            target_runtime_seconds=self._runtime(target_runtime_seconds),
            continuity_in=continuity_in.strip(),
            continuity_out=continuity_out.strip(),
            production_constraints=self._values(production_constraints),
        )
        self._write((*self.list_plans(), plan))
        return plan

    def update(
        self,
        episode_id: str,
        *,
        title: str,
        story_scope: str,
        production_objective: str,
        target_runtime_seconds: int,
        continuity_in: str,
        continuity_out: str,
        production_constraints: tuple[str, ...],
    ) -> EpisodePlan:
        """Update an editable draft without changing episode identity or Story ownership."""
        current = self._require_plan(episode_id)
        if current.status is not EpisodePlanStatus.DRAFT:
            raise EpisodePlanningError("Ready episode plans must return to Draft before editing")
        updated = replace(
            current,
            title=self._required(title, "Episode title"),
            story_scope=self._required(story_scope, "Story scope"),
            production_objective=self._required(production_objective, "Production objective"),
            target_runtime_seconds=self._runtime(target_runtime_seconds),
            continuity_in=continuity_in.strip(),
            continuity_out=continuity_out.strip(),
            production_constraints=self._values(production_constraints),
        )
        self._replace(updated)
        return updated

    def mark_ready(self, episode_id: str) -> EpisodePlan:
        """Make a complete episode plan available to Scene Planning."""
        current = self._require_plan(episode_id)
        self._validate_ready(current)
        updated = replace(current, status=EpisodePlanStatus.READY)
        self._replace(updated)
        return updated

    def return_to_draft(self, episode_id: str) -> EpisodePlan:
        """Return a Ready plan to editable Draft state."""
        current = self._require_plan(episode_id)
        updated = replace(current, status=EpisodePlanStatus.DRAFT)
        self._replace(updated)
        return updated

    def delete(self, episode_id: str) -> bool:
        """Delete only a Draft episode plan."""
        current = self.plan(episode_id)
        if current is None:
            return False
        if current.status is not EpisodePlanStatus.DRAFT:
            raise EpisodePlanningError("Ready episode plans must return to Draft before deletion")
        remaining = tuple(plan for plan in self.list_plans() if plan.episode_id != current.episode_id)
        self._write(remaining)
        return True

    def _validate_ready(self, plan: EpisodePlan) -> None:
        if not plan.story_scope.strip() or not plan.production_objective.strip():
            raise EpisodePlanningError("Episode scope and production objective are required")
        if plan.target_runtime_seconds <= 0:
            raise EpisodePlanningError("Target runtime must be greater than zero")

    def _require_story(self, story_id: str) -> None:
        if self.stories.story(story_id) is None:
            raise EpisodePlanningError(f"Story not found: {story_id}")

    def _require_plan(self, episode_id: str) -> EpisodePlan:
        plan = self.plan(episode_id)
        if plan is None:
            raise EpisodePlanningError(f"Episode plan not found: {episode_id}")
        return plan

    def _replace(self, updated: EpisodePlan) -> None:
        plans = tuple(
            updated if plan.episode_id == updated.episode_id else plan
            for plan in self.list_plans()
        )
        self._write(plans)

    def _write(self, plans: tuple[EpisodePlan, ...]) -> None:
        path = self.planning_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(plans, key=lambda plan: (plan.sequence_number, plan.episode_id))
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "episodes": [self._to_dict(plan) for plan in ordered],
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
            raise EpisodePlanningError(f"Unable to save episode plans: {exc}") from exc

    @staticmethod
    def _to_dict(plan: EpisodePlan) -> dict[str, Any]:
        raw = asdict(plan)
        raw["status"] = plan.status.value
        raw["production_constraints"] = list(plan.production_constraints)
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> EpisodePlan:
        return EpisodePlan(
            episode_id=str(raw["episode_id"]).strip().upper(),
            story_id=str(raw["story_id"]),
            sequence_number=int(raw["sequence_number"]),
            title=str(raw["title"]),
            story_scope=str(raw["story_scope"]),
            production_objective=str(raw["production_objective"]),
            target_runtime_seconds=int(raw["target_runtime_seconds"]),
            continuity_in=str(raw.get("continuity_in", "")),
            continuity_out=str(raw.get("continuity_out", "")),
            production_constraints=tuple(str(value) for value in raw.get("production_constraints", [])),
            status=EpisodePlanStatus(str(raw.get("status", EpisodePlanStatus.DRAFT.value))),
        )

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise EpisodePlanningError(f"{label} is required")
        return normalized

    @staticmethod
    def _runtime(value: int) -> int:
        if value <= 0:
            raise EpisodePlanningError("Target runtime must be greater than zero")
        return value

    @staticmethod
    def _values(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value.strip() for value in values if value.strip()))
