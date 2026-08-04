"""Renderer-neutral quality profile definitions and registry."""

from __future__ import annotations

from dataclasses import dataclass

from .models import AudioMode, LipSyncIntent, QualityLevel, RenderSettings


@dataclass(frozen=True, slots=True)
class QualityProfile:
    """Reusable renderer-neutral production quality intent."""

    level: QualityLevel
    render: RenderSettings
    audio_mode: AudioMode
    lip_sync_intent: LipSyncIntent
    priority: int


class QualityProfileRegistry:
    """Store approved quality profiles by level."""

    def __init__(self, profiles: tuple[QualityProfile, ...] = ()) -> None:
        self._profiles: dict[QualityLevel, QualityProfile] = {
            profile.level: profile for profile in profiles
        }

    def register(self, profile: QualityProfile) -> QualityProfile:
        """Register or replace one quality profile."""
        self._profiles[profile.level] = profile
        return profile

    def require(self, level: QualityLevel) -> QualityProfile:
        """Return one profile or raise when unavailable."""
        try:
            return self._profiles[level]
        except KeyError as exc:
            raise KeyError(f"Quality profile not registered: {level.value}") from exc

    def all(self) -> tuple[QualityProfile, ...]:
        """Return profiles in stable quality order."""
        return tuple(self._profiles[level] for level in QualityLevel if level in self._profiles)


def default_quality_profiles() -> tuple[QualityProfile, ...]:
    """Return the approved initial Preview and Production profiles."""
    return (
        QualityProfile(
            level=QualityLevel.PREVIEW,
            render=RenderSettings(
                width=960,
                height=400,
                frames_per_second=24,
                frame_count=120,
                sampling_effort=1,
                reference_strength=0.8,
                upscale=False,
            ),
            audio_mode=AudioMode.DRAFT,
            lip_sync_intent=LipSyncIntent.DRAFT,
            priority=50,
        ),
        QualityProfile(
            level=QualityLevel.PRODUCTION,
            render=RenderSettings(
                width=1920,
                height=800,
                frames_per_second=24,
                frame_count=120,
                sampling_effort=3,
                reference_strength=1.0,
                upscale=True,
            ),
            audio_mode=AudioMode.FINAL,
            lip_sync_intent=LipSyncIntent.FINAL,
            priority=100,
        ),
    )
