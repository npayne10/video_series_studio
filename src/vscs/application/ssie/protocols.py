"""Planning contracts for the Scene and Shot Intelligence Engine."""
from __future__ import annotations

from typing import Protocol

from .models import Scene, ScenePlan, ShotPlan


class ScenePlanner(Protocol):
    """Convert structured scene input into a scene-level production plan."""

    def plan_scene(self, scene: Scene) -> ScenePlan:
        """Plan one scene without generating prompts or rendering media."""
        ...


class ShotPlanner(Protocol):
    """Decompose structured scene input into ordered cinematic shots."""

    def plan_shots(self, scene: Scene) -> tuple[ShotPlan, ...]:
        """Return the ordered shots required to express a scene."""
        ...


class ShotProductionPlannerContract(Protocol):
    """Enrich shot plans with camera, lighting, blocking, and continuity intent."""

    def enrich_scene_plan(self, plan: ScenePlan) -> ScenePlan:
        """Return a production-enriched copy of the scene plan."""
        ...
