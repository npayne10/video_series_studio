"""LTX-2.5 Candidate C with governed provider audio for Phase 20.18.2.2i."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from vscs.application.production_execution import (
    CompiledProductionPackage,
    GovernedClosingBoundaryFrame,
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
    GovernedIntroductionKeyframeError,
    GovernedShotBoundaryError,
    GovernedShotBoundaryStore,
    GovernedShotKeyframeError,
    GovernedShotKeyframeStore,
    IntroductionIdentityCandidateStatus,
    IntroductionInjectionCandidateStatus,
    IntroductionKeyframeRequirementPlan,
    ProductionExecutionError,
    ProductionExecutionResult,
    ProductionPackageCompilationState,
    ProviderExecutionReadiness,
    ProviderExecutionReadinessState,
    ProductionPackageStatus,
    ProviderAudioPolicy,
    ProviderAudioPolicyError,
    ProviderPolicyProfile,
    ShotBoundaryAuthorityStatus,
    TimedCanonicalReferenceActivationError,
    TimedCanonicalReferenceActivationPlan,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    normalize_execution_profile,
    provider_video_rebaseline_contract,
    resolve_provider_audio_policy,
)
from vscs.application.production_execution.provider_prompt import ProductionProviderPromptCompiler
from vscs.application.production_tasks import ProductionTask
from vscs.application.provider_execution import DurableExecutionJob, ProviderExecutionOutput
from vscs.application.rendering import RenderRequest
from vscs.application.rendering.workflows import (
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)
from vscs.domain.generated_media import GeneratedMediaKind, GeneratedMediaState
from vscs.infrastructure.rendering import (
    ComfyUIWorkflowCompiler,
    ProductionPackageComfyUIAdapter,
)

from .automated_introduction_boundary import (
    ComfyUIIntroductionBoundarySynthesizer,
)
from .automated_span_orchestration import (
    AutomatedSpanOrchestrationError,
    AutomatedTimedSpanOrchestrationService,
)
from .automated_span_provider import (
    AutomatedSpanProviderError,
    LTX25AutomatedSpanProvider,
)
from .current_authority_backend import (
    CurrentAuthorityLTX23V721ProductionPackageCompilationService,
)
from .current_authority_backend import (
    LocalComfyUIProductionExecutionBackend as _CurrentAuthorityBackend,
)
from .introduction_asset_injection import ComfyUIIntroductionInjectionSynthesizer
from .ltx25_keyframe_contract import (
    LTX25_KEYFRAME_LOADER_CLASS,
    LTX25_KEYFRAME_LOADER_TITLE,
    LTX25_KEYFRAME_MANIFEST_FILE,
    LTX25_KEYFRAME_SCHEMA,
    LTX25_KEYFRAME_WORKFLOW_FILE,
    LTX25_KEYFRAME_WORKFLOW_ID,
)
from .ltx25_span_conditioning import (
    LTX25SpanConditioningError,
    LTX25SpanProviderConditioningCompiler,
)
from .minimax_h3_automated_execution import (
    MiniMaxH3AutomatedExecutionError,
    MiniMaxH3AutomatedExecutionService,
)
from .package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)
from .provider_audio_runtime import ProviderAudioGovernanceRuntime
from .provider_policy_profiles import (
    LTX25_CANDIDATE_C_POLICY_PROFILE_ID,
    MINIMAX_H3_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)
from .provider_policy_selection_store import (
    ProviderPolicySelectionError,
    ProviderPolicySelectionStore,
)
from .provider_production_adoption_store import (
    ProviderProductionAdoptionError,
    ProviderProductionAdoptionStore,
)
from .shot_boundary_runtime import GovernedShotBoundaryRuntime, GovernedShotBoundaryRuntimeError
from .timed_span_acceptance_service import (
    TimedSpanFunctionalAcceptanceService,
    TimedSpanFunctionalAcceptanceServiceError,
)


@dataclass(frozen=True, slots=True)
class LTX25GovernedKeyframeDeploymentAssurance:
    """Verify the committed Candidate C API workflow before live execution."""

    workflow_root: Path

    def inspect(self) -> tuple[str, ...]:
        workflow = self.workflow_root / LTX25_KEYFRAME_WORKFLOW_FILE
        if not workflow.is_file():
            return (f"LTX-2.5 governed-keyframe workflow is not installed at {workflow}",)
        try:
            raw = json.loads(workflow.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return (f"LTX-2.5 governed-keyframe workflow is invalid JSON: {exc}",)
        if not isinstance(raw, dict) or not raw:
            return ("LTX-2.5 governed-keyframe API workflow must be a non-empty object",)

        issues: list[str] = []
        loader = raw.get("1")
        inputs = loader.get("inputs") if isinstance(loader, dict) else None
        if (
            not isinstance(loader, dict)
            or loader.get("class_type") != LTX25_KEYFRAME_LOADER_CLASS
            or not isinstance(loader.get("_meta"), dict)
            or loader["_meta"].get("title") != LTX25_KEYFRAME_LOADER_TITLE
        ):
            issues.append("Candidate C governed-keyframe package loader node 1 is missing")
        elif not isinstance(inputs, dict):
            issues.append("Candidate C package loader inputs must be an object")
        else:
            if inputs.get("production_package") != "":
                issues.append("Candidate C checked-in production_package input must remain blank")
            if inputs.get("strict_validation") is not True:
                issues.append("Candidate C strict package validation must remain enabled")

        i2v = raw.get("13")
        i2v_inputs = i2v.get("inputs") if isinstance(i2v, dict) else None
        if not isinstance(i2v, dict) or i2v.get("class_type") != "LTXVImgToVideoInplace":
            issues.append("Candidate C LTXVImgToVideoInplace node 13 is missing")
        elif not isinstance(i2v_inputs, dict) or i2v_inputs.get("image") != ["9", 0]:
            issues.append("Candidate C I2V must consume the governed keyframe preprocess output")

        model = raw.get("4")
        model_inputs = model.get("inputs") if isinstance(model, dict) else None
        if not isinstance(model_inputs, dict) or model_inputs.get("unet_name") != (
            r"ltx2.5\ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"
        ):
            issues.append(
                "Candidate C workflow must use the approved LTX-2.5 INT8 ConvRot distilled model"
            )

        audio_vae = raw.get("2")
        audio_inputs = audio_vae.get("inputs") if isinstance(audio_vae, dict) else None
        if not isinstance(audio_inputs, dict) or audio_inputs.get("vae_name") != (
            r"ltx2.5\ltx-2.5-audio-vae-bf16.safetensors"
        ):
            issues.append("Candidate C workflow must use the approved LTX-2.5 audio VAE")

        video_vae = raw.get("3")
        video_inputs = video_vae.get("inputs") if isinstance(video_vae, dict) else None
        if not isinstance(video_inputs, dict) or video_inputs.get("vae_name") != (
            r"ltx2.5\ltx-2.5-video-vae-conv-bf16.safetensors"
        ):
            issues.append(
                "Candidate C workflow must use the approved LTX-2.5 convolutional video VAE"
            )

        text_encoder = raw.get("5")
        text_inputs = text_encoder.get("inputs") if isinstance(text_encoder, dict) else None
        if not isinstance(text_inputs, dict) or text_inputs.get("clip_name") != (
            r"ltx2.5\gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"
        ):
            issues.append(
                "Candidate C workflow must use the approved LTX-2.5 INT8 ConvRot text encoder"
            )

        prompt = raw.get("6")
        prompt_inputs = prompt.get("inputs") if isinstance(prompt, dict) else None
        if not isinstance(prompt_inputs, dict) or prompt_inputs.get("text") != ["1", 1]:
            issues.append("Candidate C positive conditioning must use motion-only package output")

        normalizer = raw.get("23")
        normalizer_inputs = normalizer.get("inputs") if isinstance(normalizer, dict) else None
        if (
            not isinstance(normalizer, dict)
            or normalizer.get("class_type") != "VSCSGovernedOutputNormalizerV721"
            or not isinstance(normalizer_inputs, dict)
            or normalizer_inputs.get("governed_frame_count") != ["1", 6]
        ):
            issues.append("Candidate C governed output normalization is missing or miswired")
        return tuple(issues)


class CurrentAuthorityLTX25GovernedKeyframeCompilationService(
    CurrentAuthorityLTX23V721ProductionPackageCompilationService
):
    """Compile current READY authority into fail-closed LTX-2.5 Candidate C packages."""

    def status(
        self,
        task: ProductionTask,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        base = super().status(task, profile=profile)
        if (
            base.state is ProductionPackageCompilationState.INVALID
            and "Shot Boundary Keyframe authority is stale" in base.message
        ):
            return replace(
                base,
                state=ProductionPackageCompilationState.STALE,
                message=(
                    "Compiled Production Package is stale because inherited Shot Boundary "
                    "Keyframe authority changed. Recompile before execution."
                ),
            )
        return base

    def validate_file(self, task: ProductionTask, path: Path) -> None:
        LocalProductionPackageCompilationService.validate_file(self, task, path)
        raw = self._read_json(path)
        if raw.get("schema_version") != LTX25_KEYFRAME_SCHEMA:
            raise LocalProductionPackageCompilationError(
                "Production Package is not compiled for Phase 20.18.2.2i LTX-2.5 Candidate C"
            )
        keyframe = raw.get("governed_keyframe")
        if not isinstance(keyframe, dict) or keyframe.get("status") != "approved":
            raise LocalProductionPackageCompilationError(
                "Candidate C Production Package has no approved governed Shot Composition Keyframe"
            )
        rebaseline = raw.get("provider_video_rebaseline")
        if not isinstance(rebaseline, dict) or rebaseline.get("active_candidate") != "C":
            raise LocalProductionPackageCompilationError(
                "Candidate C Production Package does not declare active provider candidate C"
            )
        try:
            ProviderAudioPolicy.from_dict(raw.get("provider_audio_policy"))
        except ProviderAudioPolicyError as exc:
            raise LocalProductionPackageCompilationError(
                f"Candidate C Production Package has invalid provider audio authority: {exc}"
            ) from exc

        production_authority = raw.get("production_authority")
        if not isinstance(production_authority, dict):
            raise LocalProductionPackageCompilationError(
                "Candidate C Production Package has no structured production authority"
            )
        if task.shot_id is None:
            raise LocalProductionPackageCompilationError(
                "Candidate C ProductionTask has no shot identity for boundary validation"
            )
        try:
            GovernedShotBoundaryStore(self.project_directory).validate_compiled_opening(
                task.shot_id,
                production_authority,
                raw.get("shot_boundary_continuity"),
            )
        except GovernedShotBoundaryError as exc:
            raise LocalProductionPackageCompilationError(
                f"Candidate C Shot Boundary Keyframe authority is stale or invalid: {exc}"
            ) from exc

    def _comfyui_payload(self, compiled):  # type: ignore[no-untyped-def, override]
        dynamic_spans = False
        if compiled.internal_render_spans is not None:
            try:
                span_plan = GovernedInternalRenderSpanPlan.from_dict(compiled.internal_render_spans)
                dynamic_spans = span_plan.span_count > 1
                if dynamic_spans:
                    self._validate_dynamic_span_authority(compiled, span_plan)
            except GovernedInternalRenderSpanError as exc:
                raise LocalProductionPackageCompilationError(
                    f"LTX-2.5 Candidate C internal span authority is invalid: {exc}"
                ) from exc

        content = (
            LocalProductionPackageCompilationService._base_payload_content(compiled)
            if dynamic_spans
            else LocalProductionPackageCompilationService._comfyui_payload(compiled)
        )
        boundary_store = GovernedShotBoundaryStore(self.project_directory)
        try:
            opening = boundary_store.resolve_opening(
                compiled.shot_id,
                compiled.production_authority,
            )
        except GovernedShotBoundaryError as exc:
            raise LocalProductionPackageCompilationError(
                f"LTX-2.5 Candidate C Shot Boundary Keyframe authority cannot resolve: {exc}"
            ) from exc

        if opening.inherited:
            if opening.source_shot_id is None or opening.image_path is None:
                raise LocalProductionPackageCompilationError(
                    "Inherited Shot Boundary Keyframe authority is incomplete"
                )
            closing = boundary_store.require_current_closing(opening.source_shot_id)
            image_path = boundary_store.resolve_image(closing.image_path)
            governed_keyframe = {
                "schema_version": "1.0",
                "shot_id": compiled.shot_id,
                "image_path": str(image_path),
                "image_sha256": closing.image_sha256,
                "approved_by": closing.published_by,
                "approved_at": closing.published_at,
                "acceptance_criteria": ["inherited_from_approved_closing_boundary"],
                "status": "approved",
                "source_kind": "governed_closing_boundary",
                "source_shot_id": closing.shot_id,
                "boundary_id": closing.boundary_id,
                "source_media_id": closing.source_media_id,
                "source_media_sha256": closing.source_media_sha256,
                "frame_index": closing.frame_index,
                "frame_count": closing.frame_count,
            }
            scene_composition_source = "approved_closing_boundary"
        else:
            try:
                keyframe_store = GovernedShotKeyframeStore(self.project_directory)
                keyframe = keyframe_store.require_approved(compiled.shot_id)
            except GovernedShotKeyframeError as exc:
                raise LocalProductionPackageCompilationError(
                    "LTX-2.5 Candidate C is fail-closed until a governed Shot Composition "
                    f"Keyframe is approved: {exc}"
                ) from exc
            image_path = keyframe_store.image_path(keyframe)
            governed_keyframe = {
                **keyframe.to_dict(),
                "image_path": str(image_path),
                "source_kind": "human_approved_shot_composition",
            }
            scene_composition_source = "human_approved_governed_keyframe"

        provider_frames = self._provider_frame_count(compiled.frame_count)
        content["schema_version"] = LTX25_KEYFRAME_SCHEMA
        content["status"] = "READY"
        content["positive_prompt"] = compiled.motion_prompt
        content["shot_prompt"] = compiled.motion_prompt
        content["motion_prompt"] = compiled.motion_prompt
        content["negative_prompt"] = compiled.negative_prompt
        content["keyframe_strength"] = 0.9
        content["governed_keyframe"] = governed_keyframe
        content["shot_boundary_continuity"] = opening.to_dict()
        content["provider_prompt_contract"] = {
            "schema_version": "3.0",
            "compiler": ProductionProviderPromptCompiler.COMPILER_ID,
            "mode": "motion_only_v2",
            "source": "approved_structured_production_authority",
            "scene_composition_source": scene_composition_source,
            "motion_prompt_word_count": len(compiled.motion_prompt.split()),
            "motion_prompt_max_words": ProductionProviderPromptCompiler.MAX_MOTION_WORDS,
            "combined_identity_video_reference": False,
        }
        content["provider_video_rebaseline"] = provider_video_rebaseline_contract(
            governed_keyframe_ready=True
        )
        audio_policy = resolve_provider_audio_policy(compiled.production_authority)
        content["provider_audio_policy"] = audio_policy.to_dict()
        if dynamic_spans:
            content["status"] = "TIMED_SPAN_ACCEPTANCE_REQUIRED"
            content["provider_execution_plan"] = {
                "provider": "ltx-2.5",
                "mode": "governed_multi_span_automated_orchestration",
                "governed_frame_count": compiled.frame_count,
                "provider_frame_count": provider_frames,
                "governed_duration_seconds": compiled.frame_count / compiled.frames_per_second,
                "hidden_segmentation": True,
                "keyframe_conditioning": "per_span_governed_keyframe_i2v",
                "introduction_boundary_synthesis": "qwen_image_edit_2511",
                "character_enter_boundary_authority": ("identity_locked_asset_injection_v3_6_2"),
                "automatic_provider_submission": True,
                "monolithic_submission_permitted": False,
                "manual_recovery_controls": True,
            }
        else:
            content["provider_execution_plan"] = {
                "provider": "ltx-2.5",
                "mode": "monolithic",
                "governed_frame_count": compiled.frame_count,
                "provider_frame_count": provider_frames,
                "governed_duration_seconds": compiled.frame_count / compiled.frames_per_second,
                "hidden_segmentation": False,
                "keyframe_conditioning": "first_frame_i2v",
            }
        content.pop("reference_plan", None)
        manifest = content.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise LocalProductionPackageCompilationError(
                "Candidate C Production Package has no VSCS compilation manifest"
            )
        payload = dict(content)
        payload.pop("_vscs_manifest", None)
        manifest["package_fingerprint"] = self._fingerprint(payload)
        manifest["compiler"] = (
            "VSCS Phase 20.18.2.3.6 / LTX-2.5 automated timed-span orchestration"
            if dynamic_spans
            else "VSCS Phase 20.18.2.2i / LTX-2.5 Candidate C + governed shot boundaries"
        )
        return content

    @staticmethod
    def _validate_dynamic_span_authority(
        compiled: CompiledProductionPackage,
        spans: GovernedInternalRenderSpanPlan,
    ) -> None:
        if compiled.timed_asset_presence is None:
            raise LocalProductionPackageCompilationError(
                "Dynamic Candidate C package has no Timed Asset Presence authority"
            )
        if compiled.timed_reference_activation is None:
            raise LocalProductionPackageCompilationError(
                "Dynamic Candidate C package has no Timed Canonical Reference Activation"
            )
        if compiled.introduction_keyframe_requirements is None:
            raise LocalProductionPackageCompilationError(
                "Dynamic Candidate C package has no Introduction Keyframe requirements"
            )
        try:
            timed = TimedAssetPresencePlan.from_dict(compiled.timed_asset_presence)
            spans.require_source(timed)
            activation = TimedCanonicalReferenceActivationPlan.from_dict(
                compiled.timed_reference_activation
            )
            if (
                activation.shot_id != timed.shot_id
                or activation.shot_id != spans.shot_id
                or activation.source_timed_asset_presence_plan_id != timed.plan_id
                or activation.source_timed_asset_presence_fingerprint != timed.fingerprint
                or activation.source_internal_render_span_plan_id != spans.plan_id
                or activation.source_internal_render_span_fingerprint != spans.fingerprint
            ):
                raise LocalProductionPackageCompilationError(
                    "Dynamic Candidate C timed reference activation is stale against its "
                    "structural authority"
                )
            requirements = IntroductionKeyframeRequirementPlan.from_dict(
                compiled.introduction_keyframe_requirements
            )
            requirements.require_sources(spans, activation)
        except (
            TimedAssetPresenceError,
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
            GovernedIntroductionKeyframeError,
        ) as exc:
            raise LocalProductionPackageCompilationError(
                f"Dynamic Candidate C timed-span authority is invalid: {exc}"
            ) from exc

    def compile_span_provider_conditioning(
        self,
        compiled: CompiledProductionPackage,
    ) -> dict[str, object]:
        """Compile approved Phase 20.18.2.3.4 span conditioning without executing it."""
        try:
            return (
                LTX25SpanProviderConditioningCompiler(self.project_directory)
                .compile(compiled)
                .to_dict()
            )
        except LTX25SpanConditioningError as exc:
            raise LocalProductionPackageCompilationError(
                f"LTX-2.5 governed span conditioning cannot compile: {exc}"
            ) from exc

    @staticmethod
    def _provider_frame_count(governed_frames: int) -> int:
        if governed_frames <= 0:
            raise LocalProductionPackageCompilationError(
                "Governed frame count must be positive for LTX-2.5 Candidate C"
            )
        candidate = governed_frames
        remainder = (candidate - 1) % 8
        if remainder:
            candidate += 8 - remainder
        return candidate


class LocalComfyUIProductionExecutionBackend(_CurrentAuthorityBackend):
    """Execute Phase 20.18.2.2i Candidate C with governed opening/closing boundaries."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            project_directory,
            endpoint=endpoint,
            comfyui_output_directory=comfyui_output_directory,
            managed_media_directory=managed_media_directory,
            lease_duration_seconds=lease_duration_seconds,
        )
        self.package_compilation = CurrentAuthorityLTX25GovernedKeyframeCompilationService(
            self.project_directory
        )
        self.provider_policy_registry = default_provider_policy_profile_registry()
        self.provider_policy_selections = ProviderPolicySelectionStore(self.project_directory)
        self.provider_production_adoptions = ProviderProductionAdoptionStore(
            self.project_directory
        )

    def provider_policy_profiles(self) -> tuple[ProviderPolicyProfile, ...]:
        """Expose enabled governed video-provider profiles to the normal execution UI."""
        return self.provider_policy_registry.enabled_profiles

    def provider_policy_profile_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> ProviderPolicyProfile:
        self._require_task(task_id)
        try:
            return self.provider_policy_selections.selected_profile(task_id, profile)
        except ProviderPolicySelectionError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def select_provider_policy_profile_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        provider_profile_id: str,
    ) -> ProviderPolicyProfile:
        self._require_task(task_id)
        try:
            return self.provider_policy_selections.select(
                task_id,
                profile,
                provider_profile_id,
            )
        except ProviderPolicySelectionError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def provider_execution_readiness_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> ProviderExecutionReadiness:
        """Preflight the selected provider against current governed production authority."""
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            provider_profile = self.provider_policy_selections.selected_profile(
                task.task_id,
                normalized,
            )
            package_status = self.package_compilation.status(task, profile=normalized)
            package_fingerprint = package_status.package_fingerprint or "unavailable"
            shot_id = task.shot_id or task.task_id
            blockers: list[str] = []
            provider_plan_id: str | None = None
            provider_plan_fingerprint: str | None = None

            if not package_status.executable or package_status.path is None:
                blockers.append(
                    package_status.message or "Compile the current Production Package first."
                )
                readiness = ProviderExecutionReadiness(
                    task_id=task.task_id,
                    shot_id=shot_id,
                    execution_profile=normalized,
                    provider_profile_id=provider_profile.profile_id,
                    provider_profile_fingerprint=provider_profile.fingerprint,
                    execution_adapter_id=provider_profile.execution_adapter_id,
                    package_fingerprint=package_fingerprint,
                    timed_span_state=TimedSpanAcceptanceState.PACKAGE_REQUIRED.value,
                    span_count=0,
                    requirement_count=0,
                    approved_keyframe_count=0,
                    state=ProviderExecutionReadinessState.BLOCKED,
                    blockers=tuple(blockers),
                )
                return self.provider_production_adoptions.save_readiness(readiness)

            timed_status = self.timed_span_acceptance_status_for_profile(
                task.task_id,
                profile=normalized,
            )
            if not timed_status.applicable:
                blockers.append(
                    "Selected provider orchestration currently requires a governed multi-span Shot."
                )
            if timed_status.pending_keyframe_requirement_ids:
                blockers.append(
                    f"{len(timed_status.pending_keyframe_requirement_ids)} governed "
                    "Introduction Keyframe approval(s) remain."
                )

            state = ProviderExecutionReadinessState.BLOCKED
            if timed_status.accepted:
                state = ProviderExecutionReadinessState.ACCEPTED
            elif timed_status.assembly_present:
                state = ProviderExecutionReadinessState.QC_REQUIRED
            elif not blockers:
                compiled = self.package_compilation.compile_current(
                    task,
                    profile=normalized,
                )
                package_fingerprint = compiled.package_fingerprint
                if provider_profile.profile_id == MINIMAX_H3_POLICY_PROFILE_ID:
                    comfyui_output_directory = self.comfyui_output_directory
                    if comfyui_output_directory is None:
                        blockers.append(
                            "Configure the ComfyUI output folder before H3 provider preflight."
                        )
                    else:
                        comfyui_input_directory = (
                            comfyui_output_directory.parent / "input"
                        ).resolve(strict=False)
                        if not comfyui_input_directory.is_dir():
                            blockers.append(
                                "MiniMax H3 requires the ComfyUI input folder beside the "
                                f"configured output folder: {comfyui_input_directory}"
                            )
                        else:
                            preflight = MiniMaxH3AutomatedExecutionService(
                                self.project_directory,
                                endpoint=self.endpoint,
                                comfyui_input_directory=comfyui_input_directory,
                                comfyui_output_directory=comfyui_output_directory,
                                task_repository=self.tasks,
                                package_compiler=self.package_compilation,
                                policy_profile=provider_profile,
                                execution_profile=normalized,
                            ).preflight(task.task_id)
                            provider_plan_id = preflight.plan_id
                            provider_plan_fingerprint = preflight.plan_fingerprint
                elif provider_profile.profile_id == LTX25_CANDIDATE_C_POLICY_PROFILE_ID:
                    payload = self.package_compilation.compile_span_provider_conditioning(
                        compiled
                    )
                    provider_plan_id = str(payload.get("plan_id") or "").strip() or None
                    provider_plan_fingerprint = (
                        str(payload.get("fingerprint") or "").strip() or None
                    )
                else:
                    blockers.append(
                        "Selected provider profile has no governed production preflight adapter: "
                        f"{provider_profile.profile_id}"
                    )

                if not blockers:
                    state = ProviderExecutionReadinessState.READY

            readiness = ProviderExecutionReadiness(
                task_id=task.task_id,
                shot_id=shot_id,
                execution_profile=normalized,
                provider_profile_id=provider_profile.profile_id,
                provider_profile_fingerprint=provider_profile.fingerprint,
                execution_adapter_id=provider_profile.execution_adapter_id,
                package_fingerprint=package_fingerprint,
                timed_span_state=timed_status.state.value,
                span_count=timed_status.span_count,
                requirement_count=timed_status.requirement_count,
                approved_keyframe_count=timed_status.approved_keyframe_count,
                state=state,
                blockers=tuple(blockers),
                provider_plan_id=provider_plan_id,
                provider_plan_fingerprint=provider_plan_fingerprint,
            )
            return self.provider_production_adoptions.save_readiness(readiness)
        except (
            LocalProductionPackageCompilationError,
            MiniMaxH3AutomatedExecutionError,
            ProviderPolicySelectionError,
            ProviderProductionAdoptionError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def publish_closing_boundary_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        published_by: str,
    ) -> GovernedClosingBoundaryFrame:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        candidates = tuple(
            media
            for media in self.media.list_for_task(task.task_id)
            if self.execution_profiles.profile_for_execution(media.provenance.execution_id)
            == normalized
            and media.kind is GeneratedMediaKind.VIDEO
            and media.state is GeneratedMediaState.APPROVED
        )
        if not candidates:
            raise ProductionExecutionError(
                f"No APPROVED {normalized} Generated Media video is available to publish "
                "a closing Shot Boundary Keyframe."
            )
        if len(candidates) != 1:
            raise ProductionExecutionError(
                f"Closing Shot Boundary publication is ambiguous: {len(candidates)} APPROVED "
                f"{normalized} videos exist for {task.task_id}. Supersede media before publishing "
                "continuity authority."
            )
        try:
            return GovernedShotBoundaryRuntime(
                self.project_directory,
                self.media,
            ).publish_closing(
                candidates[0].media_id,
                published_by=published_by,
            )
        except GovernedShotBoundaryRuntimeError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def shot_boundary_status_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> ShotBoundaryAuthorityStatus:
        task = self._require_task(task_id)
        if task.shot_id is None:
            raise ProductionExecutionError(
                "ProductionTask has no shot identity for Shot Boundary Keyframes."
            )
        normalized = normalize_execution_profile(profile)
        package = self.package_compilation.status(task, profile=normalized)
        production_authority: dict[str, object] = {}
        compiled_opening: object = None
        if package.path is not None and package.path.is_file():
            raw = self.package_compilation._read_json(package.path)
            authority = raw.get("production_authority")
            if isinstance(authority, dict):
                production_authority = authority
            compiled_opening = raw.get("shot_boundary_continuity")

        store = GovernedShotBoundaryStore(self.project_directory)
        opening_mode = store.resolve_opening(task.shot_id, {}).mode
        opening_state = "not_compiled"
        source_shot_id = None
        opening_boundary_id = None
        messages: list[str] = []
        if production_authority:
            try:
                opening = store.resolve_opening(task.shot_id, production_authority)
                opening_mode = opening.mode
                source_shot_id = opening.source_shot_id
                opening_boundary_id = opening.boundary_id
                if compiled_opening is not None:
                    store.validate_compiled_opening(
                        task.shot_id,
                        production_authority,
                        compiled_opening,
                    )
                opening_state = "inherited" if opening.inherited else "independent"
            except GovernedShotBoundaryError as exc:
                opening_state = "stale"
                messages.append(str(exc))

        closing_state = "not_published"
        closing_boundary_id = None
        closing_frame_index = None
        closing_frame_count = None
        if store.current_closing(task.shot_id) is not None:
            try:
                closing = store.require_current_closing(task.shot_id)
                closing_state = "published"
                closing_boundary_id = closing.boundary_id
                closing_frame_index = closing.frame_index
                closing_frame_count = closing.frame_count
            except GovernedShotBoundaryError as exc:
                closing_state = "stale"
                messages.append(str(exc))

        return ShotBoundaryAuthorityStatus(
            shot_id=task.shot_id,
            opening_mode=opening_mode,
            opening_state=opening_state,
            opening_source_shot_id=source_shot_id,
            opening_boundary_id=opening_boundary_id,
            closing_state=closing_state,
            closing_boundary_id=closing_boundary_id,
            closing_frame_index=closing_frame_index,
            closing_frame_count=closing_frame_count,
            message=" ".join(messages),
        )

    @staticmethod
    def _workflow_root() -> Path:
        return Path(__file__).resolve().parents[4] / "resources" / "workflows"

    def compile_package(
        self,
        task_id: str,
        *,
        profile: str = "production",
    ) -> ProductionPackageStatus:
        issues = LTX25GovernedKeyframeDeploymentAssurance(self._workflow_root()).inspect()
        if issues:
            raise ProductionExecutionError(
                "LTX-2.5 Candidate C workflow assurance failed: " + "; ".join(issues)
            )
        try:
            return self.package_compilation.compile(self._require_task(task_id), profile=profile)
        except LocalProductionPackageCompilationError as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def timed_span_acceptance_status_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        package = self.package_compilation.status(task, profile=normalized)
        if not package.executable or package.path is None:
            return TimedSpanAcceptanceStatus(
                shot_id=task.shot_id or task.task_id,
                state=TimedSpanAcceptanceState.PACKAGE_REQUIRED,
                span_count=0,
                boundary_count=0,
                requirement_count=0,
                approved_keyframe_count=0,
                qc_passed_count=0,
                assembly_present=False,
                message=package.message or "Compile the current Production Package first.",
            )
        try:
            provider_profile = self.provider_policy_selections.selected_profile(
                task.task_id,
                normalized,
            )
            return TimedSpanFunctionalAcceptanceService(self.project_directory).status(
                package.path,
                direct_approved_keyframes=(
                    provider_profile.profile_id == MINIMAX_H3_POLICY_PROFILE_ID
                ),
            )
        except (
            ProviderPolicySelectionError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def run_automated_timed_span_orchestration_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> TimedSpanAcceptanceStatus:
        """Execute governed spans through the operator-selected provider policy profile."""
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        readiness = self.provider_execution_readiness_for_profile(
            task.task_id,
            profile=normalized,
        )
        if not readiness.ready_to_execute:
            detail = "; ".join(readiness.blockers) or readiness.state.value
            raise ProductionExecutionError(
                "Provider-selectable production is not ready to execute: " + detail
            )
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            provider_profile = self.provider_policy_selections.selected_profile(
                task.task_id,
                normalized,
            )
            if provider_profile.profile_id == LTX25_CANDIDATE_C_POLICY_PROFILE_ID:
                if self.comfyui_output_directory is None:
                    raise ProductionExecutionError(
                        "Configure the ComfyUI output folder before automated span orchestration."
                    )
                span_provider = LTX25AutomatedSpanProvider(
                    self.project_directory,
                    endpoint=self.endpoint,
                    comfyui_output_directory=self.comfyui_output_directory,
                )
                synthesizer = ComfyUIIntroductionBoundarySynthesizer(
                    self.project_directory,
                    base_url=self.endpoint,
                )
                injection_synthesizer = ComfyUIIntroductionInjectionSynthesizer(
                    self.project_directory,
                    base_url=self.endpoint,
                )
                result = AutomatedTimedSpanOrchestrationService(
                    self.project_directory,
                    span_provider=span_provider,
                    synthesizer=synthesizer,
                    injection_synthesizer=injection_synthesizer,
                    managed_media_directory=self.managed_media_directory,
                ).run(package.path)
                status = result.acceptance_status
            elif provider_profile.profile_id == MINIMAX_H3_POLICY_PROFILE_ID:
                comfyui_output_directory = self.comfyui_output_directory
                if comfyui_output_directory is None:
                    raise ProductionExecutionError(
                        "Configure the ComfyUI output folder before H3 span orchestration."
                    )
                comfyui_input_directory = (
                    comfyui_output_directory.parent / "input"
                ).resolve(strict=False)
                if not comfyui_input_directory.is_dir():
                    raise ProductionExecutionError(
                        "MiniMax H3 requires the ComfyUI input folder beside the configured "
                        f"output folder: {comfyui_input_directory}"
                    )
                MiniMaxH3AutomatedExecutionService(
                    self.project_directory,
                    endpoint=self.endpoint,
                    comfyui_input_directory=comfyui_input_directory,
                    comfyui_output_directory=comfyui_output_directory,
                    task_repository=self.tasks,
                    package_compiler=self.package_compilation,
                    policy_profile=provider_profile,
                    execution_profile=normalized,
                ).execute(task.task_id)
                status = TimedSpanFunctionalAcceptanceService(self.project_directory).status(
                    package.path,
                    direct_approved_keyframes=True,
                )
            else:
                raise ProductionExecutionError(
                    "Selected provider policy profile has no normal Production Execution adapter: "
                    f"{provider_profile.profile_id}"
                )

            if not status.assembly_present or not status.final_path:
                raise ProductionExecutionError(
                    "Provider-selectable production completed without governed assembled media."
                )
            self.provider_production_adoptions.record_generated(
                readiness,
                final_path=status.final_path,
                final_frame_count=status.final_frame_count,
                state=(
                    "accepted"
                    if status.accepted
                    else "generated_pending_visual_qc"
                ),
            )
            return status
        except (
            LocalProductionPackageCompilationError,
            AutomatedSpanProviderError,
            AutomatedSpanOrchestrationError,
            MiniMaxH3AutomatedExecutionError,
            ProviderPolicySelectionError,
            ProviderProductionAdoptionError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def introduction_identity_gate_required_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> bool:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).identity_gate_required(package.path)
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def introduction_identity_candidate_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> IntroductionIdentityCandidateStatus | None:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(self.project_directory).identity_candidate(
                package.path
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def introduction_injection_candidate_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> IntroductionInjectionCandidateStatus | None:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(self.project_directory).injection_candidate(
                package.path
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def approve_introduction_injection_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        approved_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).approve_injection_candidate(
                package.path,
                requirement_id=requirement_id,
                approved_by=approved_by,
                notes=notes,
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def reject_introduction_injection_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        rejected_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).reject_injection_candidate(
                package.path,
                requirement_id=requirement_id,
                rejected_by=rejected_by,
                notes=notes,
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def approve_introduction_identity_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        approved_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).approve_identity_candidate(
                package.path,
                requirement_id=requirement_id,
                approved_by=approved_by,
                notes=notes,
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def reject_introduction_identity_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        rejected_by: str,
        notes: str = "",
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).reject_identity_candidate(
                package.path,
                requirement_id=requirement_id,
                rejected_by=rejected_by,
                notes=notes,
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def approve_introduction_keyframe_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        image_path: Path,
        source_boundary_image_path: Path,
        approved_by: str,
        approved_at: str,
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).approve_introduction_keyframe(
                package.path,
                requirement_id=requirement_id,
                image_path=image_path,
                source_boundary_image_path=source_boundary_image_path,
                approved_by=approved_by,
                approved_at=approved_at,
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def build_timed_span_packages_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
    ) -> tuple[Path, ...]:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(self.project_directory).build_span_packages(
                package.path
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def assemble_timed_span_outputs_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        span_paths: tuple[Path, ...],
        output_path: Path,
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            return TimedSpanFunctionalAcceptanceService(self.project_directory).assemble_outputs(
                package.path,
                span_paths=span_paths,
                output_path=output_path,
            )
        except (
            LocalProductionPackageCompilationError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def record_timed_span_qc_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        requirement_id: str,
        absent_before_boundary: bool,
        present_from_target_frame: bool,
        source_continuity_preserved: bool,
        no_unapproved_assets: bool,
        approved_by: str,
        notes: str,
    ) -> TimedSpanAcceptanceStatus:
        task = self._require_task(task_id)
        normalized = normalize_execution_profile(profile)
        try:
            package = self.package_compilation.require_current(task, profile=normalized)
            assert package.path is not None
            provider_profile = self.provider_policy_selections.selected_profile(
                task.task_id,
                normalized,
            )
            status = TimedSpanFunctionalAcceptanceService(
                self.project_directory
            ).record_visual_qc(
                package.path,
                requirement_id=requirement_id,
                absent_before_boundary=absent_before_boundary,
                present_from_target_frame=present_from_target_frame,
                source_continuity_preserved=source_continuity_preserved,
                no_unapproved_assets=no_unapproved_assets,
                approved_by=approved_by,
                notes=notes,
                direct_approved_keyframes=(
                    provider_profile.profile_id == MINIMAX_H3_POLICY_PROFILE_ID
                ),
            )
            if (
                status.accepted
                and self.provider_production_adoptions.adoption_for(
                    task.task_id,
                    normalized,
                )
                is not None
            ):
                self.provider_production_adoptions.mark_accepted(
                    task.task_id,
                    normalized,
                    approved_by=approved_by,
                    final_path=status.final_path,
                    final_frame_count=status.final_frame_count,
                )
            return status
        except (
            LocalProductionPackageCompilationError,
            ProviderPolicySelectionError,
            ProviderProductionAdoptionError,
            TimedSpanFunctionalAcceptanceServiceError,
        ) as exc:
            raise ProductionExecutionError(str(exc)) from exc

    def start(
        self,
        task_id: str,
        *,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        status = self.timed_span_acceptance_status_for_profile(
            task_id,
            profile="production",
        )
        if status.applicable and status.state is not TimedSpanAcceptanceState.PACKAGE_REQUIRED:
            raise ProductionExecutionError(
                "Dynamic timed-span Shots cannot use monolithic provider execution. "
                "Use Phase 20.18.2.3.6 automated timed-span orchestration or the manual "
                "Phase 20.18.2.3.5 recovery controls."
            )
        return super().start(task_id, production_package=production_package)

    def start_for_profile(
        self,
        task_id: str,
        *,
        profile: str,
        production_package: Path | None = None,
    ) -> ProductionExecutionResult:
        status = self.timed_span_acceptance_status_for_profile(task_id, profile=profile)
        if status.applicable and status.state is not TimedSpanAcceptanceState.PACKAGE_REQUIRED:
            raise ProductionExecutionError(
                "Dynamic timed-span Shots cannot use monolithic Start Production. "
                "Use Phase 20.18.2.3.6 automated span orchestration; manual Phase 20.18.2.3.5 "
                "controls remain available only as governed recovery paths."
            )
        return super().start_for_profile(
            task_id,
            profile=profile,
            production_package=production_package,
        )

    def _workflow_foundation(self) -> ProductionPackageComfyUIAdapter:
        workflow_root = self._workflow_root()
        manifest_path = workflow_root / "manifests" / LTX25_KEYFRAME_MANIFEST_FILE
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProductionExecutionError(
                f"Cannot load LTX-2.5 Candidate C workflow manifest: {exc}"
            ) from exc
        registry = WorkflowRegistry()
        registry.register(WorkflowManifest.from_dict(raw))
        return ProductionPackageComfyUIAdapter(
            registry,
            WorkflowCompatibilityValidator(),
            ComfyUIWorkflowCompiler(workflow_root),
            production_package_class_type=LTX25_KEYFRAME_LOADER_CLASS,
            production_package_title=LTX25_KEYFRAME_LOADER_TITLE,
            submission_audit_directory=(
                self.project_directory / ".vscs" / "provider_executions" / "payload_audit"
            ),
        )

    def _prepare_outputs_for_ingestion(
        self,
        task: ProductionTask,
        execution: DurableExecutionJob,
        outputs: tuple[ProviderExecutionOutput, ...],
    ) -> tuple[tuple[ProviderExecutionOutput, ...], Path, str]:
        profile = self.execution_profiles.profile_for_execution(execution.execution_id)
        status = self.package_compilation.require_current(task, profile=profile)
        if status.path is None:
            raise ProductionExecutionError(
                "Governed provider audio requires the current compiled Production Package"
            )
        raw = self.package_compilation._read_json(status.path)
        try:
            policy = ProviderAudioPolicy.from_dict(raw.get("provider_audio_policy"))
        except ProviderAudioPolicyError as exc:
            raise ProductionExecutionError(
                f"Governed provider audio policy cannot be resolved: {exc}"
            ) from exc
        runtime = ProviderAudioGovernanceRuntime()
        governed = runtime.apply(
            policy,
            execution_id=execution.execution_id,
            outputs=outputs,
            source_root=self._require_comfyui_output_directory(),
            staging_root=(
                self.project_directory
                / ".vscs"
                / "provider_executions"
                / "audio_governance"
                / execution.execution_id
            ),
        )
        return governed.outputs, governed.source_root, governed.note

    @staticmethod
    def _render_request(task: ProductionTask) -> RenderRequest:
        request = _CurrentAuthorityBackend._render_request(task)
        metadata = dict(request.metadata)
        metadata.update(
            {
                "generation_mode": "image_to_video",
                "start_frame_source": "governed_keyframe",
            }
        )
        return replace(
            request,
            workflow_id=LTX25_KEYFRAME_WORKFLOW_ID,
            metadata=metadata,
        )
