"""Core models for Advanced Clip Production Packages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AssetBindingRole(StrEnum):
    """Production role fulfilled by one canonical asset binding."""

    SUBJECT = "subject"
    LOCATION = "location"
    PROP = "prop"
    VEHICLE = "vehicle"
    EFFECT = "effect"
    REFERENCE = "reference"
    PROFILE = "profile"


class RenderQualityMode(StrEnum):
    """Provider-neutral render quality intent."""

    PREVIEW = "preview"
    PRODUCTION = "production"
    MASTER = "master"


class SeedPolicy(StrEnum):
    """Policy used by a future renderer when selecting generation seeds."""

    FIXED = "fixed"
    DERIVED = "derived"
    RANDOM = "random"


@dataclass(frozen=True, slots=True)
class ClipIdentity:
    """Stable production identity for one clip package."""

    clip_id: str
    production_id: str
    episode_id: str
    scene_id: str
    shot_id: str
    clip_sequence_number: int = 1


@dataclass(frozen=True, slots=True)
class RenderSpecification:
    """Renderer-neutral technical requirements for one clip."""

    width: int
    height: int
    frames_per_second: int
    frame_count: int
    quality_mode: RenderQualityMode = RenderQualityMode.PRODUCTION
    seed_policy: SeedPolicy = SeedPolicy.DERIVED
    fixed_seed: int | None = None

    @property
    def duration_seconds(self) -> float:
        """Return the requested clip duration in seconds."""
        return self.frame_count / self.frames_per_second


@dataclass(frozen=True, slots=True)
class AssetBinding:
    """Bind one approved production asset to a clip role."""

    asset_id: str
    role: AssetBindingRole
    required: bool = True
    canonical_reference_ids: tuple[str, ...] = ()
    behaviour_package_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromptSpecification:
    """Structured prompt intent without provider-specific syntax."""

    positive_visual_intent: str
    negative_constraints: tuple[str, ...] = ()
    camera_language: str = ""
    lighting_intent: str = ""
    behaviour_intent: str = ""
    environment_intent: str = ""
    continuity_intent: str = ""


@dataclass(frozen=True, slots=True)
class ContinuityBinding:
    """Clip-boundary state required for visual continuity."""

    incoming_clip_id: str | None = None
    start_reference_id: str | None = None
    end_reference_id: str | None = None
    requirements: tuple[str, ...] = ()
    outgoing_state: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AudioSpecification:
    """Provider-neutral audio requirements for one clip."""

    dialogue_lines: tuple[str, ...] = ()
    voice_profile_ids: tuple[str, ...] = ()
    ambience_profile_id: str | None = None
    music_cue_id: str | None = None
    sound_effect_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OutputSpecification:
    """Relative output naming and packaging requirements."""

    relative_directory: str
    filename_stem: str
    container: str = "mp4"

    @property
    def relative_path(self) -> str:
        """Return the normalized relative output path."""
        directory = self.relative_directory.strip("/\\")
        filename = f"{self.filename_stem}.{self.container}"
        return f"{directory}/{filename}" if directory else filename


@dataclass(frozen=True, slots=True)
class ClipProductionPackage:
    """Complete renderer-neutral production contract for one clip."""

    identity: ClipIdentity
    render: RenderSpecification
    assets: tuple[AssetBinding, ...]
    prompt: PromptSpecification
    continuity: ContinuityBinding
    audio: AudioSpecification
    output: OutputSpecification
    schema_version: str = "1.0"
    dependencies: tuple[str, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)
