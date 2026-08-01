"""Deterministic scene-level production planning for SSIE."""
from __future__ import annotations

from .models import Scene, ScenePlan
from .protocols import ShotPlanner
from .shot_planner import RuleBasedShotPlanner
from .validator import SSIEValidationIssue, SSIEValidator


class ScenePlanningError(ValueError):
    """Raised when a scene cannot be converted into a valid scene plan."""

    def __init__(self, issues: tuple[SSIEValidationIssue, ...]) -> None:
        self.issues = issues
        summary = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        super().__init__(summary or "SSIE scene planning failed.")


class RuleBasedScenePlanner:
    """Produce a deterministic scene plan without AI or render dependencies."""

    def __init__(
        self,
        shot_planner: ShotPlanner | None = None,
        validator: SSIEValidator | None = None,
    ) -> None:
        self._shot_planner = shot_planner or RuleBasedShotPlanner()
        self._validator = validator or SSIEValidator()

    def plan_scene(self, scene: Scene) -> ScenePlan:
        """Interpret one structured scene and return a validated scene plan."""
        scene_result = self._validator.validate_scene(scene)
        if not scene_result.passed:
            raise ScenePlanningError(tuple(scene_result.issues))

        plan = ScenePlan(
            scene=scene,
            objective=self._derive_objective(scene),
            emotional_intent=self._derive_emotional_intent(scene),
            shots=self._shot_planner.plan_shots(scene),
            required_asset_ids=self._required_asset_ids(scene),
            continuity_requirements=self._continuity_requirements(scene),
            production_notes=self._production_notes(scene),
        )
        plan_result = self._validator.validate_scene_plan(plan)
        if not plan_result.passed:
            raise ScenePlanningError(tuple(plan_result.issues))
        return plan

    @staticmethod
    def _derive_objective(scene: Scene) -> str:
        summary = " ".join(scene.summary.split())
        return f"Dramatise the scene outcome: {summary}"

    @staticmethod
    def _derive_emotional_intent(scene: Scene) -> str:
        text = f"{scene.heading} {scene.summary} {' '.join(scene.dialogue)}".lower()
        mappings = (
            (("danger", "threat", "attack", "alarm", "fear"), "Sustained tension"),
            (("discover", "reveal", "wonder", "mystery"), "Controlled wonder"),
            (("grief", "loss", "death", "mourning"), "Restrained grief"),
            (("conflict", "argue", "confront", "demand"), "Interpersonal tension"),
            (("hope", "relief", "reunion", "welcome"), "Measured optimism"),
        )
        for keywords, intent in mappings:
            if any(keyword in text for keyword in keywords):
                return intent
        return "Grounded dramatic clarity"

    @staticmethod
    def _required_asset_ids(scene: Scene) -> tuple[str, ...]:
        values = (
            scene.location_asset_id,
            *scene.participant_asset_ids,
            *scene.required_asset_ids,
        )
        return tuple(dict.fromkeys(value for value in values if value.strip()))

    @staticmethod
    def _continuity_requirements(scene: Scene) -> tuple[str, ...]:
        requirements = [
            f"Preserve the approved canonical state of {scene.location_asset_id}.",
        ]
        if scene.participant_asset_ids:
            requirements.append(
                "Preserve participant identity, wardrobe, props, and blocking continuity."
            )
        if scene.time_of_day:
            requirements.append(
                f"Preserve {scene.time_of_day.strip()} environmental continuity."
            )
        return tuple(requirements)

    @staticmethod
    def _production_notes(scene: Scene) -> tuple[str, ...]:
        notes = [
            f"Enter with a {scene.transition_in.value.replace('_', ' ')} transition.",
            "Use only approved canonical assets and production profiles.",
        ]
        if scene.dialogue:
            notes.append("Protect dialogue clarity, eye-lines, and editorial coverage.")
        else:
            notes.append("Prioritise visual storytelling over explanatory coverage.")
        return tuple(notes)
