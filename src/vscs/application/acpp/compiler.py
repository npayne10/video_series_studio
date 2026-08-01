"""Compile approved SSIE production plans into validated ACPP packages."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.ssie import ProductionPlan, ScenePlan, ShotPlan

from .builder import ACPPBuildError, ClipProductionPackageBuilder
from .identifiers import build_clip_id
from .models import (
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderQualityMode,
    RenderSpecification,
    SeedPolicy,
)


class ACPPCompilationError(ValueError):
    """Raised when an SSIE production plan cannot be compiled into ACPPs."""


@dataclass(frozen=True, slots=True)
class ACPPCompilerConfig:
    """Renderer-neutral defaults used while compiling clip packages."""

    width: int = 1920
    height: int = 800
    frames_per_second: int = 24
    quality_mode: RenderQualityMode = RenderQualityMode.PRODUCTION
    seed_policy: SeedPolicy = SeedPolicy.DERIVED
    output_root: str = "production"
    minimum_frame_count: int = 1

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("render dimensions must be greater than zero")
        if self.width % 2 or self.height % 2:
            raise ValueError("render dimensions must be even numbers")
        if self.frames_per_second <= 0:
            raise ValueError("frames_per_second must be greater than zero")
        if self.minimum_frame_count < 1:
            raise ValueError("minimum_frame_count must be at least 1")
        if not self.output_root.strip():
            raise ValueError("output_root must not be empty")


class SSIEToACPPCompiler:
    """Compile one validated ACPP package for every approved SSIE shot."""

    def __init__(
        self,
        config: ACPPCompilerConfig | None = None,
        builder: ClipProductionPackageBuilder | None = None,
    ) -> None:
        self.config = config or ACPPCompilerConfig()
        self._builder = builder or ClipProductionPackageBuilder()

    def compile(self, plan: ProductionPlan) -> tuple[ClipProductionPackage, ...]:
        """Compile all scenes and shots in deterministic production order."""
        if not plan.production_id.strip():
            raise ACPPCompilationError("production_id must not be empty")
        if not plan.episode_id.strip():
            raise ACPPCompilationError("episode_id must not be empty")
        if not plan.scene_plans:
            raise ACPPCompilationError("production plan must contain at least one scene")

        packages: list[ClipProductionPackage] = []
        previous_clip_id: str | None = None
        for scene_plan in plan.scene_plans:
            for shot in scene_plan.shots:
                package = self._compile_shot(
                    plan,
                    scene_plan,
                    shot,
                    previous_clip_id,
                )
                try:
                    package = self._builder.build(package)
                except ACPPBuildError as exc:
                    raise ACPPCompilationError(
                        f"Unable to compile shot {shot.shot_id}: {exc}"
                    ) from exc
                packages.append(package)
                previous_clip_id = package.identity.clip_id
        return tuple(packages)

    def _compile_shot(
        self,
        plan: ProductionPlan,
        scene_plan: ScenePlan,
        shot: ShotPlan,
        previous_clip_id: str | None,
    ) -> ClipProductionPackage:
        self._require_enriched_shot(shot)
        scene = scene_plan.scene
        clip_id = build_clip_id(
            plan.production_id,
            scene.sequence_number,
            shot.sequence_number,
        )
        frame_count = self._frame_count(shot)
        dependencies = () if previous_clip_id is None else (previous_clip_id,)
        return ClipProductionPackage(
            identity=ClipIdentity(
                clip_id=clip_id,
                production_id=plan.production_id,
                episode_id=plan.episode_id,
                scene_id=scene.scene_id,
                shot_id=shot.shot_id,
            ),
            render=RenderSpecification(
                width=self.config.width,
                height=self.config.height,
                frames_per_second=self.config.frames_per_second,
                frame_count=frame_count,
                quality_mode=self.config.quality_mode,
                seed_policy=self.config.seed_policy,
            ),
            assets=self._asset_bindings(scene_plan, shot),
            prompt=self._prompt_specification(scene_plan, shot),
            continuity=self._continuity_binding(shot, previous_clip_id),
            audio=self._audio_specification(scene_plan, shot),
            output=OutputSpecification(
                relative_directory=(
                    f"{self.config.output_root}/{plan.episode_id}/{scene.scene_id}"
                ),
                filename_stem=clip_id,
            ),
            dependencies=dependencies,
            metadata={
                "source": "ssie",
                "scene_sequence": str(scene.sequence_number),
                "shot_sequence": str(shot.sequence_number),
                "shot_purpose": shot.purpose.value,
            },
        )

    def _frame_count(self, shot: ShotPlan) -> int:
        duration = shot.estimated_duration_seconds
        if duration is None:
            raise ACPPCompilationError(
                f"Shot {shot.shot_id} does not declare an estimated duration"
            )
        frames = round(duration * self.config.frames_per_second)
        return max(self.config.minimum_frame_count, frames)

    @staticmethod
    def _require_enriched_shot(shot: ShotPlan) -> None:
        if any(
            value is None
            for value in (
                shot.camera_plan,
                shot.lighting_plan,
                shot.blocking_plan,
                shot.continuity_plan,
            )
        ):
            raise ACPPCompilationError(
                f"Shot {shot.shot_id} is missing camera, lighting, "
                "blocking, or continuity planning"
            )

    @staticmethod
    def _asset_bindings(
        scene_plan: ScenePlan,
        shot: ShotPlan,
    ) -> tuple[AssetBinding, ...]:
        scene = scene_plan.scene
        roles: dict[str, AssetBindingRole] = {
            scene.location_asset_id: AssetBindingRole.LOCATION,
        }
        roles.update(
            dict.fromkeys(
                scene.participant_asset_ids,
                AssetBindingRole.SUBJECT,
            )
        )
        for asset_id in shot.required_asset_ids:
            roles.setdefault(asset_id, AssetBindingRole.PROP)
        return tuple(
            AssetBinding(
                asset_id=asset_id,
                role=role,
                behaviour_package_ids=(
                    shot.behaviour_package_ids
                    if role is AssetBindingRole.SUBJECT
                    else ()
                ),
            )
            for asset_id, role in roles.items()
            if asset_id.strip()
        )

    @staticmethod
    def _prompt_specification(
        scene_plan: ScenePlan,
        shot: ShotPlan,
    ) -> PromptSpecification:
        camera = shot.camera_plan
        lighting = shot.lighting_plan
        blocking = shot.blocking_plan
        continuity = shot.continuity_plan
        assert camera is not None
        assert lighting is not None
        assert blocking is not None
        assert continuity is not None
        camera_language = (
            f"{camera.shot_size.value}; {camera.angle.value}; "
            f"{camera.movement.value}; {camera.lens_family.value}; "
            f"{camera.composition}; {camera.focus_strategy}."
        )
        lighting_intent = (
            f"{lighting.mood.value}; key {lighting.key_direction}; "
            f"contrast {lighting.contrast}."
        )
        behaviour_intent = " ".join(
            f"{subject.asset_id}: {subject.action} at {subject.position}."
            for subject in blocking.subjects
        )
        return PromptSpecification(
            positive_visual_intent=shot.description,
            negative_constraints=(
                "Do not deviate from approved canonical asset identity.",
                "Do not introduce unapproved props, characters, or architecture.",
            ),
            camera_language=camera_language,
            lighting_intent=lighting_intent,
            behaviour_intent=behaviour_intent,
            environment_intent=scene_plan.scene.heading,
            continuity_intent=" ".join(
                (*shot.continuity_requirements, *continuity.incoming_requirements)
            ),
        )

    @staticmethod
    def _continuity_binding(
        shot: ShotPlan,
        previous_clip_id: str | None,
    ) -> ContinuityBinding:
        continuity = shot.continuity_plan
        assert continuity is not None
        return ContinuityBinding(
            incoming_clip_id=previous_clip_id,
            requirements=(
                *shot.continuity_requirements,
                *continuity.incoming_requirements,
            ),
            outgoing_state=continuity.outgoing_state,
        )

    @staticmethod
    def _audio_specification(
        scene_plan: ScenePlan,
        shot: ShotPlan,
    ) -> AudioSpecification:
        dialogue = scene_plan.scene.dialogue if shot.subject_asset_ids else ()
        return AudioSpecification(dialogue_lines=dialogue)
