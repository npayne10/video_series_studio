"""Configurable deterministic shot planning for SSIE scenes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import Scene, SceneTransition, ShotPlan, ShotPurpose


class ScenePurpose(StrEnum):
    """Narrative function inferred from structured scene content."""

    INTRODUCTION = "introduction"
    EXPOSITION = "exposition"
    CONFLICT = "conflict"
    REVELATION = "revelation"
    ACTION = "action"
    TRANSITION = "transition"
    RESOLUTION = "resolution"


class PacingProfile(StrEnum):
    """Editorial pacing applied to deterministic shot decomposition."""

    DELIBERATE = "deliberate"
    BALANCED = "balanced"
    URGENT = "urgent"


@dataclass(frozen=True, slots=True)
class ShotPlannerConfig:
    """Constraints and optional grammar features for shot planning."""

    maximum_shots: int = 12
    minimum_shot_duration_seconds: float = 2.0
    maximum_shot_duration_seconds: float = 15.0
    include_reaction_shots: bool = True
    include_revelation_inserts: bool = True
    include_transition_shots: bool = True

    def __post_init__(self) -> None:
        if self.maximum_shots < 2:
            raise ValueError("maximum_shots must be at least 2")
        if self.minimum_shot_duration_seconds <= 0:
            raise ValueError("minimum shot duration must be greater than zero")
        if self.maximum_shot_duration_seconds < self.minimum_shot_duration_seconds:
            raise ValueError("maximum shot duration must not be less than minimum shot duration")


@dataclass(frozen=True, slots=True)
class ShotPlanningAnalysis:
    """Deterministic interpretation used to select cinematic grammar."""

    scene_purpose: ScenePurpose
    pacing: PacingProfile


@dataclass(frozen=True, slots=True)
class _ShotSpec:
    purpose: ShotPurpose
    description: str
    subjects: tuple[str, ...] = ()


class RuleBasedShotPlanner:
    """Plan ordered cinematic coverage from structured scene information."""

    def __init__(self, config: ShotPlannerConfig | None = None) -> None:
        self.config = config or ShotPlannerConfig()

    def analyse_scene(self, scene: Scene) -> ShotPlanningAnalysis:
        """Classify scene purpose and pacing without mutating scene data."""
        text = " ".join((scene.heading, scene.summary, *scene.dialogue)).casefold()
        purpose = self._classify_purpose(scene, text)
        pacing = self._classify_pacing(scene, text, purpose)
        return ShotPlanningAnalysis(scene_purpose=purpose, pacing=pacing)

    def plan_shots(self, scene: Scene) -> tuple[ShotPlan, ...]:
        analysis = self.analyse_scene(scene)
        specs = self._build_grammar(scene, analysis)
        specs = self._limit_specs(specs)
        durations = self._allocate_durations(scene, len(specs), analysis.pacing)
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
                purpose=spec.purpose,
                description=spec.description,
                subject_asset_ids=spec.subjects,
                required_asset_ids=required_assets,
                continuity_requirements=continuity,
                estimated_duration_seconds=durations[index - 1],
            )
            for index, spec in enumerate(specs, start=1)
        )

    def _build_grammar(
        self,
        scene: Scene,
        analysis: ShotPlanningAnalysis,
    ) -> list[_ShotSpec]:
        specs = [
            _ShotSpec(
                ShotPurpose.ESTABLISHING,
                f"Establish {scene.heading.strip()} and its spatial context.",
            )
        ]

        if self.config.include_transition_shots and scene.transition_in is not SceneTransition.CUT:
            specs.append(
                _ShotSpec(
                    ShotPurpose.TRANSITION,
                    self._transition_description(scene.transition_in),
                )
            )

        if scene.dialogue:
            specs.extend(self._dialogue_coverage(scene, analysis))
        else:
            specs.extend(self._action_coverage(scene, analysis))

        if (
            self.config.include_revelation_inserts
            and analysis.scene_purpose is ScenePurpose.REVELATION
            and scene.required_asset_ids
        ):
            specs.append(
                _ShotSpec(
                    ShotPurpose.INSERT,
                    "Isolate the decisive visual detail that communicates the revelation.",
                    (scene.required_asset_ids[0],),
                )
            )

        specs.append(
            _ShotSpec(
                ShotPurpose.CLOSING,
                self._closing_description(analysis.scene_purpose),
                scene.participant_asset_ids,
            )
        )
        return specs

    def _dialogue_coverage(
        self,
        scene: Scene,
        analysis: ShotPlanningAnalysis,
    ) -> list[_ShotSpec]:
        specs = [
            _ShotSpec(
                ShotPurpose.MASTER,
                "Cover the complete dialogue exchange and participant geography.",
                scene.participant_asset_ids,
            )
        ]
        for participant_id in scene.participant_asset_ids:
            specs.append(
                _ShotSpec(
                    ShotPurpose.COVERAGE,
                    f"Provide dialogue coverage for {participant_id}.",
                    (participant_id,),
                )
            )

        if (
            self.config.include_reaction_shots
            and len(scene.participant_asset_ids) >= 2
            and analysis.scene_purpose is ScenePurpose.CONFLICT
        ):
            specs.append(
                _ShotSpec(
                    ShotPurpose.REACTION,
                    "Hold on the receiving participant to register the emotional impact.",
                    (scene.participant_asset_ids[-1],),
                )
            )
        return specs

    @staticmethod
    def _action_coverage(
        scene: Scene,
        analysis: ShotPlanningAnalysis,
    ) -> list[_ShotSpec]:
        if analysis.pacing is PacingProfile.URGENT and scene.participant_asset_ids:
            return [
                _ShotSpec(
                    ShotPurpose.ACTION,
                    "Begin the physical action with clear geography and direction.",
                    scene.participant_asset_ids,
                ),
                _ShotSpec(
                    ShotPurpose.ACTION,
                    "Escalate the action around its decisive movement or obstacle.",
                    scene.participant_asset_ids,
                ),
            ]
        return [
            _ShotSpec(
                ShotPurpose.ACTION,
                scene.summary.strip(),
                scene.participant_asset_ids,
            )
        ]

    def _limit_specs(self, specs: list[_ShotSpec]) -> list[_ShotSpec]:
        if len(specs) <= self.config.maximum_shots:
            return specs
        opening = specs[0]
        closing = specs[-1]
        available = self.config.maximum_shots - 2
        return [opening, *specs[1:-1][:available], closing]

    def _allocate_durations(
        self,
        scene: Scene,
        shot_count: int,
        pacing: PacingProfile,
    ) -> tuple[float | None, ...]:
        if scene.estimated_duration_seconds is None:
            return (None,) * shot_count

        target = scene.estimated_duration_seconds / shot_count
        if pacing is PacingProfile.URGENT:
            target *= 0.85
        elif pacing is PacingProfile.DELIBERATE:
            target *= 1.1
        duration = min(
            self.config.maximum_shot_duration_seconds,
            max(self.config.minimum_shot_duration_seconds, target),
        )
        return (round(duration, 3),) * shot_count

    @staticmethod
    def _classify_purpose(scene: Scene, text: str) -> ScenePurpose:
        if any(word in text for word in ("attack", "chase", "escape", "explosion")):
            return ScenePurpose.ACTION
        if any(word in text for word in ("argue", "threat", "conflict", "confront")):
            return ScenePurpose.CONFLICT
        if any(word in text for word in ("discover", "reveal", "realise", "secret")):
            return ScenePurpose.REVELATION
        if any(word in text for word in ("resolve", "accept", "reconcile", "farewell")):
            return ScenePurpose.RESOLUTION
        if scene.transition_in is not SceneTransition.CUT and not scene.participant_asset_ids:
            return ScenePurpose.TRANSITION
        if scene.sequence_number == 1:
            return ScenePurpose.INTRODUCTION
        return ScenePurpose.EXPOSITION

    @staticmethod
    def _classify_pacing(
        scene: Scene,
        text: str,
        purpose: ScenePurpose,
    ) -> PacingProfile:
        if purpose in {ScenePurpose.ACTION, ScenePurpose.CONFLICT} or any(
            word in text for word in ("alarm", "urgent", "imminent", "race")
        ):
            return PacingProfile.URGENT
        if purpose in {ScenePurpose.RESOLUTION, ScenePurpose.TRANSITION} or any(
            word in text for word in ("quiet", "reflect", "slowly", "grief")
        ):
            return PacingProfile.DELIBERATE
        if scene.estimated_duration_seconds and scene.estimated_duration_seconds >= 90:
            return PacingProfile.DELIBERATE
        return PacingProfile.BALANCED

    @staticmethod
    def _transition_description(transition: SceneTransition) -> str:
        return (
            f"Express the {transition.value.replace('_', ' ')} transition while preserving "
            "orientation and narrative continuity."
        )

    @staticmethod
    def _closing_description(purpose: ScenePurpose) -> str:
        if purpose is ScenePurpose.REVELATION:
            return "End on the consequence of the revealed information."
        if purpose is ScenePurpose.CONFLICT:
            return "End on the unresolved pressure created by the confrontation."
        if purpose is ScenePurpose.ACTION:
            return "Resolve the immediate action beat and establish its consequence."
        if purpose is ScenePurpose.RESOLUTION:
            return "Hold the resolved emotional state before the editorial transition."
        return "Resolve the scene visually and prepare the editorial transition."

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
            requirements.append(f"Maintain {scene.time_of_day.strip()} lighting continuity.")
        return tuple(requirements)

    @staticmethod
    def _ordered_unique(values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value.strip()))
