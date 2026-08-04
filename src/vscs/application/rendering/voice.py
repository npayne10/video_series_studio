"""Canonical voice identity and timed dialogue contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class VoiceEmotion(StrEnum):
    """Renderer-neutral emotional performance intents."""

    NEUTRAL = "neutral"
    CALM = "calm"
    WARM = "warm"
    URGENT = "urgent"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SAD = "sad"
    JOYFUL = "joyful"
    AUTHORITATIVE = "authoritative"
    WHISPERED = "whispered"


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    """Canonical reusable voice identity for one speaking character."""

    profile_id: str
    character_asset_id: str
    provider: str
    voice_id: str
    language: str
    accent: str = ""
    speaking_rate: float = 1.0
    pitch: float = 0.0
    default_emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    pronunciation_overrides: tuple[tuple[str, str], ...] = ()
    processing_profile_id: str | None = None
    version: str = "1.0"

    def __post_init__(self) -> None:
        for name, value in (
            ("profile_id", self.profile_id),
            ("character_asset_id", self.character_asset_id),
            ("provider", self.provider),
            ("voice_id", self.voice_id),
            ("language", self.language),
            ("version", self.version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not 0.25 <= self.speaking_rate <= 4.0:
            raise ValueError("speaking_rate must be between 0.25 and 4.0")
        if not -24.0 <= self.pitch <= 24.0:
            raise ValueError("pitch must be between -24 and 24 semitones")
        terms = [term for term, _replacement in self.pronunciation_overrides]
        if any(not term.strip() for term in terms):
            raise ValueError("pronunciation override terms may not be empty")
        if len(terms) != len(set(terms)):
            raise ValueError("pronunciation override terms must be unique")


@dataclass(frozen=True, slots=True)
class DialogueTiming:
    """Target timing window for one dialogue cue."""

    start_seconds: float
    end_seconds: float

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            raise ValueError("start_seconds may not be negative")
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")

    @property
    def duration_seconds(self) -> float:
        """Return the available duration for the dialogue cue."""
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class DialogueCue:
    """One timed line bound to a canonical character and voice profile."""

    cue_id: str
    character_asset_id: str
    voice_profile_id: str
    text: str
    timing: DialogueTiming
    emotion: VoiceEmotion = VoiceEmotion.NEUTRAL
    face_target_id: str | None = None
    off_screen: bool = False
    pronunciation_notes: tuple[str, ...] = ()
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("cue_id", self.cue_id),
            ("character_asset_id", self.character_asset_id),
            ("voice_profile_id", self.voice_profile_id),
            ("text", self.text),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if self.off_screen and self.face_target_id is not None:
            raise ValueError("off-screen dialogue may not declare a face target")


@dataclass(frozen=True, slots=True)
class VoiceGenerationRequest:
    """Renderer-neutral request for generating dialogue audio."""

    request_id: str
    production_id: str
    scene_id: str
    shot_id: str
    cues: tuple[DialogueCue, ...]
    output_directory: str
    version: str = "1.0"

    def __post_init__(self) -> None:
        for name, value in (
            ("request_id", self.request_id),
            ("production_id", self.production_id),
            ("scene_id", self.scene_id),
            ("shot_id", self.shot_id),
            ("version", self.version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        normalized = self.output_directory.replace("\\", "/")
        if normalized.startswith("/") or ".." in normalized.split("/"):
            raise ValueError("output_directory must remain project-relative")
        cue_ids = [cue.cue_id for cue in self.cues]
        if len(cue_ids) != len(set(cue_ids)):
            raise ValueError("dialogue cue IDs must be unique")
        ordered = sorted(self.cues, key=lambda cue: cue.timing.start_seconds)
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.timing.start_seconds < previous.timing.end_seconds:
                raise ValueError("dialogue cue timing windows may not overlap")


@dataclass(slots=True)
class VoiceProfileRegistry:
    """Registry of canonical voice profiles used across productions."""

    _profiles: dict[str, VoiceProfile] = field(default_factory=dict)

    def register(self, profile: VoiceProfile) -> None:
        """Register or replace one canonical voice profile."""
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> VoiceProfile | None:
        """Return one voice profile by identity."""
        return self._profiles.get(profile_id)

    def for_character(self, character_asset_id: str) -> tuple[VoiceProfile, ...]:
        """Return all profiles associated with one character asset."""
        return tuple(
            sorted(
                (
                    profile
                    for profile in self._profiles.values()
                    if profile.character_asset_id == character_asset_id
                ),
                key=lambda profile: profile.profile_id,
            )
        )

    def list(self) -> tuple[VoiceProfile, ...]:
        """List profiles in stable identity order."""
        return tuple(sorted(self._profiles.values(), key=lambda profile: profile.profile_id))
