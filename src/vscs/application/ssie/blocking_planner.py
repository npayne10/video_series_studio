"""Deterministic blocking planning for SSIE shots."""
from __future__ import annotations

from .models import (
    BlockingPattern,
    BlockingPlan,
    Scene,
    ShotPlan,
    ShotPurpose,
    SubjectBlocking,
)


class RuleBasedBlockingPlanner:
    """Derive subject positions, eye-lines, and movement intent."""

    def plan_blocking(self, scene: Scene, shot: ShotPlan) -> BlockingPlan:
        pattern = self._pattern(shot)
        subjects = tuple(
            SubjectBlocking(
                asset_id=asset_id,
                position=self._position(index, len(shot.subject_asset_ids), pattern),
                facing=self._facing(index, len(shot.subject_asset_ids), pattern),
                action=self._action(shot),
                eye_line_target=self._eye_line_target(
                    index,
                    shot.subject_asset_ids,
                    pattern,
                ),
            )
            for index, asset_id in enumerate(shot.subject_asset_ids)
        )
        movement_notes = self._movement_notes(scene, shot, pattern)
        return BlockingPlan(
            pattern=pattern,
            subjects=subjects,
            screen_direction="maintain established left-right geography across coverage",
            movement_notes=movement_notes,
        )

    @staticmethod
    def _pattern(shot: ShotPlan) -> BlockingPattern:
        if shot.purpose is ShotPurpose.ESTABLISHING:
            return BlockingPattern.ENVIRONMENTAL
        if shot.purpose is ShotPurpose.INSERT:
            return BlockingPattern.OBJECT_FOCUS
        if shot.purpose is ShotPurpose.REACTION:
            return BlockingPattern.REACTION
        if shot.purpose is ShotPurpose.ACTION:
            return BlockingPattern.MOVEMENT_PATH
        if len(shot.subject_asset_ids) == 1:
            return BlockingPattern.SINGLE_SUBJECT
        if len(shot.subject_asset_ids) == 2:
            return BlockingPattern.TWO_SHOT
        if len(shot.subject_asset_ids) > 2:
            return BlockingPattern.GROUP
        return BlockingPattern.ENVIRONMENTAL

    @staticmethod
    def _position(index: int, count: int, pattern: BlockingPattern) -> str:
        if pattern is BlockingPattern.OBJECT_FOCUS:
            return "featured object position"
        if count <= 1:
            return "primary action position"
        if count == 2:
            return "frame left" if index == 0 else "frame right"
        return f"group position {index + 1}"

    @staticmethod
    def _facing(index: int, count: int, pattern: BlockingPattern) -> str:
        if pattern in {BlockingPattern.TWO_SHOT, BlockingPattern.REACTION} and count > 1:
            return "toward frame right" if index == 0 else "toward frame left"
        if pattern is BlockingPattern.MOVEMENT_PATH:
            return "along the established movement vector"
        return "toward the primary dramatic focus"

    @staticmethod
    def _action(shot: ShotPlan) -> str:
        if shot.purpose is ShotPurpose.ACTION:
            return "execute the scene action through a readable movement path"
        if shot.purpose is ShotPurpose.REACTION:
            return "hold the reaction long enough to register the emotional change"
        if shot.purpose is ShotPurpose.COVERAGE:
            return "deliver or receive dialogue without crossing the established axis"
        if shot.purpose is ShotPurpose.INSERT:
            return "remain static unless story action explicitly manipulates the object"
        return "maintain the planned scene action and spatial relationship"

    @staticmethod
    def _eye_line_target(
        index: int,
        subjects: tuple[str, ...],
        pattern: BlockingPattern,
    ) -> str | None:
        if len(subjects) == 2:
            return subjects[1 - index]
        if pattern is BlockingPattern.REACTION and subjects:
            return "off-screen dramatic source"
        return None

    @staticmethod
    def _movement_notes(
        scene: Scene,
        shot: ShotPlan,
        pattern: BlockingPattern,
    ) -> tuple[str, ...]:
        notes = [f"Preserve spatial continuity within {scene.location_asset_id}."]
        if pattern is BlockingPattern.MOVEMENT_PATH:
            notes.append("Define clear start and end marks for the action beat.")
        if shot.purpose in {ShotPurpose.COVERAGE, ShotPurpose.REACTION}:
            notes.append("Do not cross the established dialogue axis.")
        return tuple(notes)
