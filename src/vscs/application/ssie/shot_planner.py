"""Deterministic shot decomposition for SSIE scenes."""
from __future__ import annotations

from .models import Scene, ShotPlan, ShotPurpose


class RuleBasedShotPlanner:
    """Create a conservative baseline shot list from structured scene data."""

    def plan_shots(self, scene: Scene) -> tuple[ShotPlan, ...]:
        shot_specs: list[tuple[ShotPurpose, str, tuple[str, ...]]] = [
            (
                ShotPurpose.ESTABLISHING,
                f"Establish {scene.heading.strip()} and its spatial context.",
                (),
            )
        ]

        if scene.dialogue:
            shot_specs.append(
                (
                    ShotPurpose.MASTER,
                    "Cover the complete dialogue exchange and participant geography.",
                    scene.participant_asset_ids,
                )
            )
            for participant_id in scene.participant_asset_ids:
                shot_specs.append(
                    (
                        ShotPurpose.COVERAGE,
                        f"Provide dialogue coverage for {participant_id}.",
                        (participant_id,),
                    )
                )
        else:
            shot_specs.append(
                (
                    ShotPurpose.ACTION,
                    scene.summary.strip(),
                    scene.participant_asset_ids,
                )
            )

        shot_specs.append(
            (
                ShotPurpose.CLOSING,
                "Resolve the scene visually and prepare the editorial transition.",
                scene.participant_asset_ids,
            )
        )

        duration = self._shot_duration(scene, len(shot_specs))
        required_assets = self._ordered_unique(
            (
                scene.location_asset_id,
                *scene.participant_asset_ids,
                *scene.required_asset_ids,
            )
        )
        continuity = self._continuity_requirements(scene)

        return tuple(
            ShotPlan(
                shot_id=f"{scene.scene_id}-S{index:03d}",
                scene_id=scene.scene_id,
                sequence_number=index,
                purpose=purpose,
                description=description,
                subject_asset_ids=subjects,
                required_asset_ids=required_assets,
                continuity_requirements=continuity,
                estimated_duration_seconds=duration,
            )
            for index, (purpose, description, subjects) in enumerate(
                shot_specs,
                start=1,
            )
        )

    @staticmethod
    def _shot_duration(scene: Scene, shot_count: int) -> float | None:
        if scene.estimated_duration_seconds is None:
            return None
        return round(scene.estimated_duration_seconds / shot_count, 3)

    @staticmethod
    def _continuity_requirements(scene: Scene) -> tuple[str, ...]:
        requirements = [
            f"Maintain location continuity for {scene.location_asset_id}.",
        ]
        if scene.participant_asset_ids:
            requirements.append(
                "Maintain participant appearance, wardrobe, and spatial continuity."
            )
        if scene.time_of_day:
            requirements.append(
                f"Maintain {scene.time_of_day.strip()} lighting continuity."
            )
        return tuple(requirements)

    @staticmethod
    def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value.strip()))
