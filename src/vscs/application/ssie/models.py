"""Core models for the Scene and Shot Intelligence Engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SceneTransition(StrEnum):
    """Supported editorial transitions into a scene."""

    CUT = "cut"
    DISSOLVE = "dissolve"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    MATCH_CUT = "match_cut"


class ShotPurpose(StrEnum):
    """High-level narrative purpose assigned to a shot."""

    ESTABLISHING = "establishing"
    MASTER = "master"
    COVERAGE = "coverage"
    REACTION = "reaction"
    INSERT = "insert"
    CUTAWAY = "cutaway"
    ACTION = "action"
    TRANSITION = "transition"
    CLOSING = "closing"


@dataclass(frozen=True, slots=True)
class Scene:
    """Structured story input consumed by SSIE planners."""

    scene_id: str
    episode_id: str
    sequence_number: int
    heading: str
    location_asset_id: str
    summary: str
    participant_asset_ids: tuple[str, ...] = ()
    dialogue: tuple[str, ...] = ()
    required_asset_ids: tuple[str, ...] = ()
    time_of_day: str | None = None
    transition_in: SceneTransition = SceneTransition.CUT
    estimated_duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ShotPlan:
    """One ordered cinematic decision inside a planned scene."""

    shot_id: str
    scene_id: str
    sequence_number: int
    purpose: ShotPurpose
    description: str
    subject_asset_ids: tuple[str, ...] = ()
    required_asset_ids: tuple[str, ...] = ()
    camera_profile_id: str | None = None
    lighting_profile_id: str | None = None
    behaviour_package_ids: tuple[str, ...] = ()
    continuity_requirements: tuple[str, ...] = ()
    estimated_duration_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class ScenePlan:
    """Approved production interpretation of one structured scene."""

    scene: Scene
    objective: str
    emotional_intent: str
    shots: tuple[ShotPlan, ...]
    required_asset_ids: tuple[str, ...] = ()
    continuity_requirements: tuple[str, ...] = ()
    production_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProductionPlan:
    """Validated SSIE output consumed by the future ACPP engine."""

    production_id: str
    episode_id: str
    scene_plans: tuple[ScenePlan, ...]
    schema_version: str = "1.0"
    warnings: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def shot_count(self) -> int:
        """Return the total number of planned shots."""
        return sum(len(scene_plan.shots) for scene_plan in self.scene_plans)
