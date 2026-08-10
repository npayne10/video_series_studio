"""Iterative Scene Planning governance correction for Phase 19.3.2.1."""

from __future__ import annotations

from dataclasses import replace

from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene

from .episode_planning import EpisodePlanningService, EpisodePlanStatus
from .scene_planning import ScenePlan, ScenePlanningError, ScenePlanningService, ScenePlanStatus
from .service import StoryService


class IterativeScenePlanningService(ScenePlanningService):
    """Allow Draft Episode/Scene iteration while protecting Shot Planning authority."""

    def __init__(
        self,
        projects: ProjectService,
        episodes: EpisodePlanningService,
        legacy_story: StoryService | None = None,
    ) -> None:
        super().__init__(projects, episodes)
        self.legacy_story = legacy_story or StoryService(projects)

    def legacy_scenes(self, episode_id: str) -> tuple[Scene, ...]:
        """Return preserved legacy scenes that have not become authoritative Scene Plans."""
        normalized = episode_id.strip().upper()
        authoritative_ids = {plan.scene_id for plan in self.list_plans(episode_id=normalized)}
        return tuple(
            scene
            for scene in self.legacy_story.list_scenes()
            if scene.episode_id.strip().upper() == normalized
            and scene.scene_id.strip().upper() not in authoritative_ids
        )

    def is_upstream_current(self, scene: ScenePlan) -> bool:
        """Return whether the Scene Plan matches the current Episode contract.

        Draft Episodes are still current planning inputs. Production readiness is
        checked separately and still requires a Ready Episode.
        """
        episode = self.episodes.plan(scene.episode_id)
        return episode is not None and scene.episode_contract_hash == self._episode_contract_hash(
            episode
        )

    def is_production_ready(self, scene: ScenePlan) -> bool:
        """Return whether Shot Planning may safely consume this Scene Plan."""
        episode = self.episodes.plan(scene.episode_id)
        return (
            scene.status is ScenePlanStatus.READY
            and episode is not None
            and episode.status is EpisodePlanStatus.READY
            and self.is_upstream_current(scene)
        )

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
        """Create an editable Draft Scene Plan beneath a Draft or Ready Episode."""
        episode = self._require_episode(episode_id)
        if sequence_number < 1:
            raise ScenePlanningError("Scene sequence number must be at least 1")
        scene_id = self._scene_id(episode.episode_id, sequence_number)
        if self.plan(scene_id) is not None:
            raise ScenePlanningError(f"Scene plan already exists: {scene_id}")
        runtime = self._runtime(target_runtime_seconds)
        self._validate_runtime_budget(episode, runtime)
        events = self._values(required_events)
        if not events:
            raise ScenePlanningError(
                "At least one required story event is needed for Shot Planning"
            )
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
        """Update a Draft Scene Plan while its Episode remains Draft or Ready."""
        current = self._require_plan(scene_id)
        if current.status is not ScenePlanStatus.DRAFT:
            raise ScenePlanningError("Ready scene plans must return to Draft before editing")
        episode = self._require_episode(current.episode_id)
        runtime = self._runtime(target_runtime_seconds)
        self._validate_runtime_budget(episode, runtime, excluding_scene_id=current.scene_id)
        events = self._values(required_events)
        if not events:
            raise ScenePlanningError(
                "At least one required story event is needed for Shot Planning"
            )
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

    @staticmethod
    def _scene_id(episode_id: str, sequence_number: int) -> str:
        return f"{episode_id}-SCN-{sequence_number:03d}"
