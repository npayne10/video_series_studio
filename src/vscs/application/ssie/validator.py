"""Validation rules for SSIE foundation models."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .models import ProductionPlan, Scene, ScenePlan, ShotPlan


class SSIEValidationSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class SSIEValidationIssue:
    severity: SSIEValidationSeverity
    code: str
    message: str
    object_id: str | None = None


@dataclass(slots=True)
class SSIEValidationResult:
    issues: list[SSIEValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(
            issue.severity is SSIEValidationSeverity.ERROR for issue in self.issues
        )


class SSIEValidator:
    """Validate model integrity without making production decisions."""

    def validate_scene(self, scene: Scene) -> SSIEValidationResult:
        result = SSIEValidationResult()
        self._require_text(result, scene.scene_id, "scene_id", scene.scene_id)
        self._require_text(result, scene.scene_id, "episode_id", scene.episode_id)
        self._require_text(result, scene.scene_id, "heading", scene.heading)
        self._require_text(
            result,
            scene.scene_id,
            "location_asset_id",
            scene.location_asset_id,
        )
        self._require_text(result, scene.scene_id, "summary", scene.summary)
        if scene.sequence_number < 1:
            self._error(
                result,
                "INVALID_SCENE_SEQUENCE",
                "Scene sequence number must be at least 1.",
                scene.scene_id,
            )
        if (
            scene.estimated_duration_seconds is not None
            and scene.estimated_duration_seconds <= 0
        ):
            self._error(
                result,
                "INVALID_SCENE_DURATION",
                "Estimated scene duration must be greater than zero.",
                scene.scene_id,
            )
        return result

    def validate_scene_plan(self, plan: ScenePlan) -> SSIEValidationResult:
        result = self.validate_scene(plan.scene)
        self._require_text(result, plan.scene.scene_id, "objective", plan.objective)
        self._require_text(
            result,
            plan.scene.scene_id,
            "emotional_intent",
            plan.emotional_intent,
        )
        if not plan.shots:
            self._error(
                result,
                "SCENE_HAS_NO_SHOTS",
                "A scene plan must contain at least one shot.",
                plan.scene.scene_id,
            )
            return result

        shot_ids: set[str] = set()
        expected_sequence = 1
        for shot in plan.shots:
            if shot.shot_id in shot_ids:
                self._error(
                    result,
                    "DUPLICATE_SHOT_ID",
                    f"Shot ID '{shot.shot_id}' is duplicated.",
                    plan.scene.scene_id,
                )
            shot_ids.add(shot.shot_id)
            if shot.scene_id != plan.scene.scene_id:
                self._error(
                    result,
                    "SHOT_SCENE_MISMATCH",
                    f"Shot '{shot.shot_id}' belongs to a different scene.",
                    shot.shot_id,
                )
            if shot.sequence_number != expected_sequence:
                self._error(
                    result,
                    "NON_CONTIGUOUS_SHOT_SEQUENCE",
                    "Shot sequence numbers must be contiguous and start at 1.",
                    shot.shot_id,
                )
            if not shot.description.strip():
                self._error(
                    result,
                    "EMPTY_SHOT_DESCRIPTION",
                    "Shot description must not be empty.",
                    shot.shot_id,
                )
            if (
                shot.estimated_duration_seconds is not None
                and shot.estimated_duration_seconds <= 0
            ):
                self._error(
                    result,
                    "INVALID_SHOT_DURATION",
                    "Estimated shot duration must be greater than zero.",
                    shot.shot_id,
                )
            self._validate_production_layers(shot, result)
            expected_sequence += 1
        return result

    def validate_production_plan(self, plan: ProductionPlan) -> SSIEValidationResult:
        result = SSIEValidationResult()
        self._require_text(
            result,
            plan.production_id,
            "production_id",
            plan.production_id,
        )
        self._require_text(
            result,
            plan.production_id,
            "episode_id",
            plan.episode_id,
        )
        self._require_text(
            result,
            plan.production_id,
            "schema_version",
            plan.schema_version,
        )
        if not plan.scene_plans:
            self._error(
                result,
                "PRODUCTION_HAS_NO_SCENES",
                "A production plan must contain at least one scene plan.",
                plan.production_id,
            )
            return result

        scene_ids: set[str] = set()
        previous_sequence = 0
        for scene_plan in plan.scene_plans:
            scene = scene_plan.scene
            if scene.scene_id in scene_ids:
                self._error(
                    result,
                    "DUPLICATE_SCENE_ID",
                    f"Scene ID '{scene.scene_id}' is duplicated.",
                    plan.production_id,
                )
            scene_ids.add(scene.scene_id)
            if scene.episode_id != plan.episode_id:
                self._error(
                    result,
                    "SCENE_EPISODE_MISMATCH",
                    f"Scene '{scene.scene_id}' belongs to a different episode.",
                    scene.scene_id,
                )
            if scene.sequence_number <= previous_sequence:
                self._error(
                    result,
                    "SCENES_NOT_ORDERED",
                    "Scene plans must be ordered by increasing sequence number.",
                    scene.scene_id,
                )
            previous_sequence = scene.sequence_number
            result.issues.extend(self.validate_scene_plan(scene_plan).issues)
        return result

    @staticmethod
    def _validate_production_layers(
        shot: ShotPlan,
        result: SSIEValidationResult,
    ) -> None:
        layers = (
            shot.camera_plan,
            shot.lighting_plan,
            shot.blocking_plan,
            shot.continuity_plan,
        )
        populated = sum(layer is not None for layer in layers)
        if populated not in {0, len(layers)}:
            SSIEValidator._error(
                result,
                "INCOMPLETE_SHOT_PRODUCTION_PLAN",
                "A shot must provide all production planning layers or none of them.",
                shot.shot_id,
            )

    @staticmethod
    def _require_text(
        result: SSIEValidationResult,
        object_id: str | None,
        field_name: str,
        value: str,
    ) -> None:
        if not value.strip():
            SSIEValidator._error(
                result,
                "REQUIRED_TEXT_MISSING",
                f"Required field '{field_name}' must not be empty.",
                object_id,
            )

    @staticmethod
    def _error(
        result: SSIEValidationResult,
        code: str,
        message: str,
        object_id: str | None,
    ) -> None:
        result.issues.append(
            SSIEValidationIssue(
                severity=SSIEValidationSeverity.ERROR,
                code=code,
                message=message,
                object_id=object_id,
            )
        )
