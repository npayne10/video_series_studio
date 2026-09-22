"""LTX-2.5 governed-keyframe Candidate C execution backend for Phase 20.18.2.2g."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from vscs.application.production_execution import (
    GovernedShotKeyframeError,
    GovernedShotKeyframeStore,
    ProductionExecutionError,
    ProductionPackageStatus,
    provider_video_rebaseline_contract,
)
from vscs.application.production_execution.provider_prompt import ProductionProviderPromptCompiler
from vscs.application.production_tasks import ProductionTask
from vscs.application.rendering import RenderRequest
from vscs.application.rendering.workflows import (
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.infrastructure.rendering import (
    ComfyUIWorkflowCompiler,
    ProductionPackageComfyUIAdapter,
)

from .current_authority_backend import (
    CurrentAuthorityLTX23V721ProductionPackageCompilationService,
)
from .current_authority_backend import (
    LocalComfyUIProductionExecutionBackend as _CurrentAuthorityBackend,
)
from .package_compilation import (
    LocalProductionPackageCompilationError,
    LocalProductionPackageCompilationService,
)

LTX25_KEYFRAME_WORKFLOW_ID = "ltx25_i2v_keyframe_v1"
LTX25_KEYFRAME_WORKFLOW_FILE = "workflows/ltx25_i2v_keyframe_v1_api.json"
LTX25_KEYFRAME_MANIFEST_FILE = "ltx25_i2v_keyframe_v1.json"
LTX25_KEYFRAME_SCHEMA = "7.2.2-vscs-1"
LTX25_KEYFRAME_LOADER_CLASS = "VSCSLTX25GovernedKeyframePackageLoaderV1"
LTX25_KEYFRAME_LOADER_TITLE = "VSCS LTX-2.5 Governed Keyframe Package Loader v1"


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
            r"ltx2.5\ltx-2.5-22b-distilled-transformer-bf16.safetensors"
        ):
            issues.append("Candidate C workflow must use the approved LTX-2.5 distilled model")

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
            issues.append("Candidate C workflow must use the approved LTX-2.5 convolutional video VAE")

        text_encoder = raw.get("5")
        text_inputs = text_encoder.get("inputs") if isinstance(text_encoder, dict) else None
        if not isinstance(text_inputs, dict) or text_inputs.get("clip_name") != (
            r"ltx2.5\gemma4-12b-with-proj-ltx-2.5-bf16.safetensors"
        ):
            issues.append("Candidate C workflow must use the approved LTX-2.5 text encoder")

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

    def validate_file(self, task: ProductionTask, path: Path) -> None:
        LocalProductionPackageCompilationService.validate_file(self, task, path)
        raw = self._read_json(path)
        if raw.get("schema_version") != LTX25_KEYFRAME_SCHEMA:
            raise LocalProductionPackageCompilationError(
                "Production Package is not compiled for Phase 20.18.2.2g LTX-2.5 Candidate C"
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

    def _comfyui_payload(self, compiled):  # type: ignore[no-untyped-def, override]
        content = LocalProductionPackageCompilationService._comfyui_payload(compiled)
        try:
            store = GovernedShotKeyframeStore(self.project_directory)
            keyframe = store.require_approved(compiled.shot_id)
        except GovernedShotKeyframeError as exc:
            raise LocalProductionPackageCompilationError(
                "LTX-2.5 Candidate C is fail-closed until a governed Shot Composition Keyframe "
                f"is approved: {exc}"
            ) from exc

        image_path = store.image_path(keyframe)
        provider_frames = self._provider_frame_count(compiled.frame_count)
        content["schema_version"] = LTX25_KEYFRAME_SCHEMA
        content["status"] = "READY"
        content["positive_prompt"] = compiled.motion_prompt
        content["shot_prompt"] = compiled.motion_prompt
        content["motion_prompt"] = compiled.motion_prompt
        content["negative_prompt"] = compiled.negative_prompt
        content["keyframe_strength"] = 0.9
        content["governed_keyframe"] = {
            **keyframe.to_dict(),
            "image_path": str(image_path),
        }
        content["provider_prompt_contract"] = {
            "schema_version": "3.0",
            "compiler": ProductionProviderPromptCompiler.COMPILER_ID,
            "mode": "motion_only_v2",
            "source": "approved_structured_production_authority",
            "scene_composition_source": "human_approved_governed_keyframe",
            "motion_prompt_word_count": len(compiled.motion_prompt.split()),
            "motion_prompt_max_words": ProductionProviderPromptCompiler.MAX_MOTION_WORDS,
            "combined_identity_video_reference": False,
        }
        content["provider_video_rebaseline"] = provider_video_rebaseline_contract(
            governed_keyframe_ready=True
        )
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
        manifest["compiler"] = "VSCS Phase 20.18.2.2g / LTX-2.5 Candidate C"
        return content

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
    """Execute Phase 20.18.2.2g Candidate C through LTX-2.5 governed-keyframe I2V."""

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

    @staticmethod
    def _render_request(task: ProductionTask) -> RenderRequest:
        request = _CurrentAuthorityBackend._render_request(task)
        return replace(request, workflow_id=LTX25_KEYFRAME_WORKFLOW_ID)
