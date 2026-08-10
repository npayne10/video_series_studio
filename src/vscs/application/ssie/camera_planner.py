"""Deterministic camera planning for SSIE shots."""

from __future__ import annotations

from .models import (
    CameraAngle,
    CameraMovement,
    CameraPlan,
    LensFamily,
    Scene,
    ShotPlan,
    ShotPurpose,
    ShotSize,
)


class RuleBasedCameraPlanner:
    """Translate shot purpose into renderer-neutral camera intent."""

    def plan_camera(self, scene: Scene, shot: ShotPlan) -> CameraPlan:
        size = self._shot_size(shot)
        return CameraPlan(
            shot_size=size,
            angle=self._angle(shot),
            movement=self._movement(scene, shot),
            lens_family=self._lens_family(size),
            camera_height=self._camera_height(shot),
            composition=self._composition(shot),
            focus_strategy=self._focus_strategy(shot),
            profile_requirements=self._profile_requirements(scene, shot),
        )

    @staticmethod
    def _shot_size(shot: ShotPlan) -> ShotSize:
        mapping = {
            ShotPurpose.ESTABLISHING: ShotSize.EXTREME_WIDE,
            ShotPurpose.MASTER: ShotSize.WIDE,
            ShotPurpose.COVERAGE: ShotSize.MEDIUM_CLOSE,
            ShotPurpose.REACTION: ShotSize.CLOSE_UP,
            ShotPurpose.INSERT: ShotSize.INSERT,
            ShotPurpose.CUTAWAY: ShotSize.MEDIUM,
            ShotPurpose.ACTION: ShotSize.WIDE,
            ShotPurpose.TRANSITION: ShotSize.WIDE,
            ShotPurpose.CLOSING: ShotSize.MEDIUM,
        }
        return mapping[shot.purpose]

    @staticmethod
    def _angle(shot: ShotPlan) -> CameraAngle:
        if shot.purpose is ShotPurpose.COVERAGE and len(shot.subject_asset_ids) == 1:
            return CameraAngle.OVER_SHOULDER
        if shot.purpose is ShotPurpose.INSERT:
            return CameraAngle.HIGH
        return CameraAngle.EYE_LEVEL

    @staticmethod
    def _movement(scene: Scene, shot: ShotPlan) -> CameraMovement:
        if shot.purpose is ShotPurpose.ESTABLISHING:
            return CameraMovement.CRANE if scene.location_asset_id else CameraMovement.STATIC
        if shot.purpose is ShotPurpose.ACTION:
            return CameraMovement.TRACK
        if shot.purpose is ShotPurpose.REACTION:
            return CameraMovement.PUSH_IN
        if shot.purpose is ShotPurpose.TRANSITION:
            return CameraMovement.PULL_BACK
        if shot.purpose is ShotPurpose.CLOSING:
            return CameraMovement.PUSH_IN
        return CameraMovement.STATIC

    @staticmethod
    def _lens_family(size: ShotSize) -> LensFamily:
        if size in {ShotSize.EXTREME_WIDE, ShotSize.WIDE}:
            return LensFamily.WIDE
        if size is ShotSize.INSERT:
            return LensFamily.MACRO
        if size in {ShotSize.CLOSE_UP, ShotSize.EXTREME_CLOSE_UP}:
            return LensFamily.PORTRAIT
        return LensFamily.NORMAL

    @staticmethod
    def _camera_height(shot: ShotPlan) -> str:
        if shot.purpose is ShotPurpose.INSERT:
            return "aligned with the featured object"
        return "subject eye level"

    @staticmethod
    def _composition(shot: ShotPlan) -> str:
        if shot.purpose is ShotPurpose.ESTABLISHING:
            return "prioritise environment scale and readable spatial geography"
        if shot.purpose is ShotPurpose.MASTER:
            return "preserve all participant positions and shared action"
        if shot.purpose in {ShotPurpose.COVERAGE, ShotPurpose.REACTION}:
            return "preserve eye-line and conversational screen direction"
        if shot.purpose is ShotPurpose.INSERT:
            return "isolate the narrative detail without unrelated visual clutter"
        return "centre narrative action with stable headroom and lead room"

    @staticmethod
    def _focus_strategy(shot: ShotPlan) -> str:
        if shot.purpose is ShotPurpose.INSERT:
            return "shallow focus on the narrative detail"
        if len(shot.subject_asset_ids) > 1:
            return "maintain readable focus across active subjects"
        return "hold primary subject focus"

    @staticmethod
    def _profile_requirements(scene: Scene, shot: ShotPlan) -> tuple[str, ...]:
        requirements = [f"support {shot.purpose.value} framing"]
        if scene.transition_in.value != "cut" and shot.sequence_number == 1:
            requirements.append(f"support {scene.transition_in.value} transition continuity")
        return tuple(requirements)
