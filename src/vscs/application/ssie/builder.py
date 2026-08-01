"""Foundation builder for assembling validated SSIE production plans."""
from __future__ import annotations

from dataclasses import replace

from .models import ProductionPlan, Scene
from .protocols import ScenePlanner
from .validator import SSIEValidationIssue, SSIEValidator


class SSIEBuildError(ValueError):
    """Raised when SSIE cannot produce a valid production plan."""

    def __init__(self, issues: tuple[SSIEValidationIssue, ...]) -> None:
        self.issues = issues
        summary = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        super().__init__(summary or "SSIE production plan validation failed.")


class ProductionPlanBuilder:
    """Coordinate scene planners and enforce the SSIE output contract."""

    def __init__(
        self,
        scene_planner: ScenePlanner,
        validator: SSIEValidator | None = None,
    ) -> None:
        self._scene_planner = scene_planner
        self._validator = validator or SSIEValidator()

    def build(
        self,
        production_id: str,
        episode_id: str,
        scenes: tuple[Scene, ...],
    ) -> ProductionPlan:
        """Plan ordered scenes and return a validated production plan."""
        scene_plans = tuple(
            self._scene_planner.plan_scene(scene)
            for scene in sorted(scenes, key=lambda item: item.sequence_number)
        )
        plan = ProductionPlan(
            production_id=production_id,
            episode_id=episode_id,
            scene_plans=scene_plans,
        )
        result = self._validator.validate_production_plan(plan)
        if not result.passed:
            raise SSIEBuildError(tuple(result.issues))
        return replace(plan, warnings=tuple(
            issue.message
            for issue in result.issues
            if issue.severity.value == "warning"
        ))
