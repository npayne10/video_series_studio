"""Persistent production-shot models for the VSCS Shot Planner."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.ssie import (
    CameraMovement,
    LensFamily,
    LightingMood,
    ShotPurpose,
    ShotSize,
)


class ShotPlanningStatus(StrEnum):
    """Production readiness state for one manually planned shot."""

    DRAFT = "draft"
    READY = "ready"
    APPROVED = "approved"

    @property
    def label(self) -> str:
        return self.value.title()


@dataclass(frozen=True, slots=True)
class ProductionShot:
    """One persistent, editable cinematic shot inside a structured scene."""

    shot_id: str
    scene_id: str
    sequence_number: int
    title: str
    description: str
    purpose: ShotPurpose = ShotPurpose.COVERAGE
    shot_size: ShotSize = ShotSize.MEDIUM
    camera_movement: CameraMovement = CameraMovement.STATIC
    lens_family: LensFamily = LensFamily.NORMAL
    camera_profile_id: str | None = None
    lighting_profile_id: str | None = None
    lighting_mood: LightingMood = LightingMood.NATURALISTIC
    estimated_duration_seconds: float = 5.0
    continuity_from_shot_id: str | None = None
    continuity_notes: str = ""
    blocking_notes: str = ""
    storyboard_reference: str = ""
    dialogue_lines: tuple[str, ...] = ()
    subject_asset_ids: tuple[str, ...] = ()
    required_asset_ids: tuple[str, ...] = ()
    status: ShotPlanningStatus = ShotPlanningStatus.DRAFT

    @property
    def ready(self) -> bool:
        """Return whether the minimum downstream production information exists."""
        return bool(
            self.title.strip() and self.description.strip() and self.estimated_duration_seconds > 0
        )


def build_shot_id(scene_id: str, sequence_number: int) -> str:
    """Build a stable shot identity from a scene and sequence number."""
    return f"{scene_id}-SHT-{sequence_number:03d}"
