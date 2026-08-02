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


class ShotSize(StrEnum):
    """Planning-level subject framing."""

    EXTREME_WIDE = "extreme_wide"
    WIDE = "wide"
    MEDIUM = "medium"
    MEDIUM_CLOSE = "medium_close"
    CLOSE_UP = "close_up"
    EXTREME_CLOSE_UP = "extreme_close_up"
    INSERT = "insert"


class CameraAngle(StrEnum):
    """Planning-level camera angle."""

    EYE_LEVEL = "eye_level"
    HIGH = "high"
    LOW = "low"
    OVER_SHOULDER = "over_shoulder"
    OVERHEAD = "overhead"
    DUTCH = "dutch"


class CameraMovement(StrEnum):
    """Planning-level camera movement intent."""

    STATIC = "static"
    PUSH_IN = "push_in"
    PULL_BACK = "pull_back"
    PAN = "pan"
    TILT = "tilt"
    TRACK = "track"
    ORBIT = "orbit"
    CRANE = "crane"
    HANDHELD_RESTRAINED = "handheld_restrained"


class LensFamily(StrEnum):
    """Lens family requested by cinematic intent."""

    ULTRA_WIDE = "ultra_wide"
    WIDE = "wide"
    NORMAL = "normal"
    PORTRAIT = "portrait"
    TELEPHOTO = "telephoto"
    MACRO = "macro"


class LightingMood(StrEnum):
    """Narrative lighting intent."""

    NATURALISTIC = "naturalistic"
    HIGH_KEY = "high_key"
    LOW_KEY = "low_key"
    TENSE = "tense"
    AWE = "awe"
    SOMBRE = "sombre"
    HOPEFUL = "hopeful"
    TRANSITIONAL = "transitional"


class BlockingPattern(StrEnum):
    """High-level spatial arrangement for subjects."""

    ENVIRONMENTAL = "environmental"
    SINGLE_SUBJECT = "single_subject"
    TWO_SHOT = "two_shot"
    GROUP = "group"
    OPPOSITIONAL = "oppositional"
    REACTION = "reaction"
    MOVEMENT_PATH = "movement_path"
    OBJECT_FOCUS = "object_focus"


@dataclass(frozen=True, slots=True)
class CameraPlan:
    """Renderer-neutral camera intent for one shot."""

    shot_size: ShotSize
    angle: CameraAngle
    movement: CameraMovement
    lens_family: LensFamily
    camera_height: str
    composition: str
    focus_strategy: str
    profile_requirements: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LightingPlan:
    """Renderer-neutral lighting intent for one shot."""

    mood: LightingMood
    key_direction: str
    contrast: str
    practical_sources: tuple[str, ...] = ()
    continuity_key: str = ""
    profile_requirements: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SubjectBlocking:
    """One subject's spatial and performance instruction."""

    asset_id: str
    position: str
    facing: str
    action: str
    eye_line_target: str | None = None


@dataclass(frozen=True, slots=True)
class BlockingPlan:
    """Spatial staging and movement intent for one shot."""

    pattern: BlockingPattern
    subjects: tuple[SubjectBlocking, ...] = ()
    screen_direction: str = "maintain established screen direction"
    movement_notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContinuityPlan:
    """Continuity state that must remain stable for one shot."""

    location_state: str
    participant_states: tuple[str, ...] = ()
    prop_states: tuple[str, ...] = ()
    lighting_state: str = ""
    screen_direction: str = ""
    incoming_requirements: tuple[str, ...] = ()
    outgoing_state: tuple[str, ...] = ()


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
    scene_name: str = ""


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
    camera_plan: CameraPlan | None = None
    lighting_plan: LightingPlan | None = None
    blocking_plan: BlockingPlan | None = None
    continuity_plan: ContinuityPlan | None = None


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
