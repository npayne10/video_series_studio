"""Coordinate camera, lighting, blocking, and continuity planning."""

from __future__ import annotations

from dataclasses import replace

from .blocking_planner import RuleBasedBlockingPlanner
from .camera_planner import RuleBasedCameraPlanner
from .continuity_planner import RuleBasedContinuityPlanner
from .lighting_planner import RuleBasedLightingPlanner
from .models import ScenePlan, ShotPlan


class ShotProductionPlanner:
    """Enrich scene shots with renderer-neutral production intent."""

    def __init__(
        self,
        camera_planner: RuleBasedCameraPlanner | None = None,
        lighting_planner: RuleBasedLightingPlanner | None = None,
        blocking_planner: RuleBasedBlockingPlanner | None = None,
        continuity_planner: RuleBasedContinuityPlanner | None = None,
    ) -> None:
        self._camera = camera_planner or RuleBasedCameraPlanner()
        self._lighting = lighting_planner or RuleBasedLightingPlanner()
        self._blocking = blocking_planner or RuleBasedBlockingPlanner()
        self._continuity = continuity_planner or RuleBasedContinuityPlanner()

    def enrich_scene_plan(self, plan: ScenePlan) -> ScenePlan:
        """Return a copy of a scene plan with every shot fully planned."""
        enriched: list[ShotPlan] = []
        previous: ShotPlan | None = None
        for shot in plan.shots:
            camera = self._camera.plan_camera(plan.scene, shot)
            lighting = self._lighting.plan_lighting(
                plan.scene,
                shot,
                plan.emotional_intent,
            )
            blocking = self._blocking.plan_blocking(plan.scene, shot)
            continuity = self._continuity.plan_continuity(
                plan.scene,
                shot,
                previous,
            )
            planned = replace(
                shot,
                camera_plan=camera,
                lighting_plan=lighting,
                blocking_plan=blocking,
                continuity_plan=continuity,
            )
            enriched.append(planned)
            previous = planned
        return replace(plan, shots=tuple(enriched))
