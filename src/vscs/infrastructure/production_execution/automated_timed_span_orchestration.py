"""Automated sequential timed-span execution for Phase 20.18.2.3.6."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.production_execution.automated_introduction_boundaries import (
    AutomatedIntroductionBoundaryError,
    AutomatedSpanExecutionResult,
    IntroductionBoundaryAutomationPlanner,
    IntroductionBoundarySynthesisRequest,
    IntroductionBoundarySynthesizer,
    IntroductionBoundaryValidator,
    TimedSpanExecutor,
)
from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirement,
    IntroductionKeyframeRequirementPlan,
)
from vscs.application.production_execution.timed_reference_activation import (
    TimedCanonicalReferenceActivationError,
    TimedCanonicalReferenceActivationPlan,
)
from vscs.application.production_execution.timed_span_acceptance import (
    TimedSpanAcceptanceError,
    TimedSpanAcceptanceEvaluator,
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
    TimedSpanAcceptanceStore,
)
from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RenderJobStatus,
    RenderRequest,
    RenderSettings,
    RendererKind,
)
from vscs.application.timed_asset_presence import (
    TimedAssetPresenceError,
    TimedAssetPresencePlan,
)
from vscs.infrastructure.rendering import LiveComfyUIAdapter

from .timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
    TimedSpanAcceptancePackageError,
)
from .timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    GovernedSpanAssemblyRuntimeError,
)


class AutomatedTimedSpanOrchestrationError(RuntimeError):
    """Raised when automatic span production cannot continue safely."""


@dataclass(frozen=True, slots=True)
class AutomatedTimedSpanOrchestrationResult:
    """Outcome of one automatic dynamic-Shot orchestration run."""

    shot_id: str
    state: TimedSpanAcceptanceState
    span_outputs: tuple[Path, ...]
    assembled_output: Path | None
    manual_review_requirement_id: str | None = None
    message: str = ""


class LTX25AutomatedSpanExecutor(TimedSpanExecutor):
    """Execute isolated Candidate C span packages without creating task retries."""

    provider_id = "comfyui.ltx-2.5.timed-span.v1"

    def __init__(
        self,
        adapter: LiveComfyUIAdapter,
        *,
        workflow_id: str,
        comfyui_output_directory: Path,
        poll_seconds: float = 1.0,
        timeout_seconds: float = 3600.0,
    ) -> None:
        self.adapter = adapter
        self.workflow_id = workflow_id
        self.output_directory = Path(comfyui_output_directory).expanduser().resolve(strict=False)
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds

    def execute(
        self,
        package_path: Path,
        *,
        span_sequence_number: int,
    ) -> AutomatedSpanExecutionResult:
        package = self._read(package_path)
        request = self._request(package, package_path, span_sequence_number)
        try:
            validation = self.adapter.validate_request(request)
            if not validation.valid:
                raise AutomatedTimedSpanOrchestrationError(
                    "Timed span render request is invalid: " + "; ".join(validation.issues)
                )
            compiled = self.adapter.compile_request(request)
            job = self.adapter.submit(compiled)
            deadline = time.monotonic() + self.timeout_seconds
            while time.monotonic() < deadline:
                job = self.adapter.monitor(job)
                if job.status is RenderJobStatus.COMPLETED:
                    break
                if job.status in {RenderJobStatus.FAILED, RenderJobStatus.CANCELLED}:
                    raise AutomatedTimedSpanOrchestrationError(
                        f"Timed span provider execution ended in {job.status.value}: "
                        f"{job.failure_reason or 'no failure detail'}"
                    )
                time.sleep(self.poll_seconds)
            else:
                raise AutomatedTimedSpanOrchestrationError(
                    f"Timed span provider execution timed out after {self.timeout_seconds:.0f}s"
                )
            outputs = self.adapter.fetch_outputs(job)
        except AutomatedTimedSpanOrchestrationError:
            raise
        except Exception as exc:
            raise AutomatedTimedSpanOrchestrationError(
                f"Timed span provider execution failed: {exc}"
            ) from exc

        videos = [
            (self.output_directory / output.relative_path).resolve(strict=False)
            for output in outputs
            if Path(output.relative_path).suffix.casefold() in {".mp4", ".mov", ".mkv", ".webm"}
        ]
        videos = [path for path in videos if path.is_relative_to(self.output_directory) and path.is_file()]
        if len(videos) != 1:
            raise AutomatedTimedSpanOrchestrationError(
                f"Expected exactly one normalized span video output, found {len(videos)}"
            )
        prompt_id = str(job.renderer_job_id or "").strip()
        if not prompt_id:
            raise AutomatedTimedSpanOrchestrationError(
                "ComfyUI span execution did not retain provider prompt identity"
            )
        return AutomatedSpanExecutionResult(
            span_sequence_number=span_sequence_number,
            package_path=Path(package_path).resolve(strict=False),
            output_path=videos[0],
            provider_id=self.provider_id,
            provider_job_id=prompt_id,
        )

    def _request(
        self,
        package: dict[str, Any],
        package_path: Path,
        span_sequence_number: int,
    ) -> RenderRequest:
        manifest = package.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise AutomatedTimedSpanOrchestrationError("Span package has no VSCS manifest")
        production_id = str(manifest.get("production_id") or "").strip()
        episode_id = str(manifest.get("episode_id") or "").strip()
        scene_id = str(manifest.get("scene_id") or "").strip()
        shot_id = str(manifest.get("shot_id") or "").strip()
        if not all((production_id, episode_id, scene_id, shot_id)):
            raise AutomatedTimedSpanOrchestrationError(
                "Span package manifest is missing production hierarchy"
            )
        frame_count = self._positive_int(package.get("frame_count"), "frame_count")
        width = self._positive_int(package.get("width"), "width")
        height = self._positive_int(package.get("height"), "height")
        fps = self._positive_int(package.get("fps"), "fps")
        seed = package.get("seed")
        seed_value = seed if isinstance(seed, int) and not isinstance(seed, bool) else None
        filename_prefix = str(package.get("filename_prefix") or shot_id).replace("\\", "/")
        output_dir = str(Path(filename_prefix).parent).replace("\\", "/")
        filename_stem = Path(filename_prefix).name or f"span-{span_sequence_number:03d}"
        return RenderRequest(
            request_id=(
                f"AUTO-SPAN-{shot_id}-{span_sequence_number:03d}-"
                f"{str(manifest.get('package_fingerprint') or '')[:12]}"
            ),
            production_id=production_id,
            container_id=episode_id,
            scene_id=scene_id,
            shot_id=shot_id,
            clip_id=f"{shot_id}-SPAN-{span_sequence_number:03d}",
            renderer=RendererKind.COMFYUI,
            workflow_id=self.workflow_id,
            quality_level=QualityLevel.PRODUCTION,
            prompt_package=PromptPackageReference(
                package_id=f"AUTO-SPAN-PROMPT-{shot_id}-{span_sequence_number:03d}"
            ),
            assets=AssetPackageReference(),
            continuity=ContinuityPackageReference(),
            render=RenderSettings(
                width=width,
                height=height,
                frames_per_second=fps,
                frame_count=frame_count,
                seed=seed_value,
            ),
            output=OutputSettings(
                relative_directory=output_dir,
                filename_stem=filename_stem,
                container="mp4",
            ),
            metadata={
                "production_package": str(Path(package_path).resolve(strict=False)),
                "generation_mode": "image_to_video",
                "start_frame_source": "governed_keyframe",
                "orchestration_mode": "automated_timed_span",
            },
        )

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        candidate = Path(path).expanduser().resolve(strict=False)
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedTimedSpanOrchestrationError(
                f"Cannot read timed span package: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise AutomatedTimedSpanOrchestrationError("Timed span package root must be an object")
        return raw

    @staticmethod
    def _positive_int(value: object, field_name: str) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        raise AutomatedTimedSpanOrchestrationError(
            f"Timed span package {field_name} must be a positive integer"
        )


class AutomatedTimedSpanOrchestrationService:
    """Run dynamic spans sequentially and synthesize introduction boundaries automatically."""

    AUTOMATION_ACTOR = "VSCS Automated Boundary Synthesis"

    def __init__(
        self,
        project_directory: Path,
        *,
        executor: TimedSpanExecutor,
        synthesizer: IntroductionBoundarySynthesizer,
        validator: IntroductionBoundaryValidator,
        ffmpeg: str = "ffmpeg",
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.executor = executor
        self.synthesizer = synthesizer
        self.validator = validator
        self.ffmpeg = ffmpeg
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)
        self.acceptance = TimedSpanAcceptanceStore(self.project_directory)
        self.evaluator = TimedSpanAcceptanceEvaluator(self.project_directory)

    def run(
        self,
        compiled_package_path: Path,
        *,
        output_path: Path | None = None,
    ) -> AutomatedTimedSpanOrchestrationResult:
        package_path = Path(compiled_package_path).expanduser().resolve(strict=False)
        raw = self._read(package_path)
        spans, activation, requirements = self._authority(raw)
        builder = LTX25TimedSpanAcceptancePackageBuilder(self.project_directory)
        requirement_by_source = {
            requirement.source_span_id: requirement for requirement in requirements.requirements
        }
        span_outputs: list[Path] = []

        for span in spans.spans:
            try:
                span_package = builder.build_span(package_path, span.sequence_number)
                execution = self.executor.execute(
                    span_package,
                    span_sequence_number=span.sequence_number,
                )
            except (TimedSpanAcceptancePackageError, AutomatedIntroductionBoundaryError) as exc:
                raise AutomatedTimedSpanOrchestrationError(str(exc)) from exc
            span_outputs.append(execution.output_path)

            requirement = requirement_by_source.get(span.span_id)
            if requirement is None:
                continue

            working = self._working_directory(requirement)
            source_frame = working / f"source-frame-{requirement.source_global_frame_index:06d}.png"
            self._extract_frame(
                execution.output_path,
                frame_index=span.frame_count - 1,
                destination=source_frame,
            )
            request = self._synthesis_request(
                raw,
                activation,
                requirement,
                source_frame,
                working,
            )
            try:
                synthesis = self.synthesizer.synthesize(request)
                validation = self.validator.validate(request, synthesis)
            except Exception as exc:
                record = self._write_automation_record(
                    requirement,
                    request,
                    synthesis=None,
                    validation=None,
                    state="manual_review_required",
                    findings=(str(exc),),
                )
                return AutomatedTimedSpanOrchestrationResult(
                    shot_id=spans.shot_id,
                    state=TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
                    span_outputs=tuple(span_outputs),
                    assembled_output=None,
                    manual_review_requirement_id=requirement.requirement_id,
                    message=(
                        "Automated Introduction Boundary synthesis/validation could not complete; "
                        f"manual review is required. Evidence: {record}"
                    ),
                )
            if not validation.passed:
                record = self._write_automation_record(
                    requirement,
                    request,
                    synthesis=synthesis,
                    validation=validation,
                    state="manual_review_required",
                    findings=validation.findings,
                )
                return AutomatedTimedSpanOrchestrationResult(
                    shot_id=spans.shot_id,
                    state=TimedSpanAcceptanceState.KEYFRAME_REQUIRED,
                    span_outputs=tuple(span_outputs),
                    assembled_output=None,
                    manual_review_requirement_id=requirement.requirement_id,
                    message=(
                        "Automated Introduction Boundary validation failed closed; "
                        f"manual review is required. Evidence: {record}"
                    ),
                )

            record = self._write_automation_record(
                requirement,
                request,
                synthesis=synthesis,
                validation=validation,
                state="validated",
                findings=(),
            )
            self._register_automated_keyframe(
                requirement,
                source_frame,
                synthesis.image_path,
                record,
            )

        destination = (
            Path(output_path)
            if output_path is not None
            else self.project_directory
            / ".vscs"
            / "timed_span_acceptance"
            / "assembled"
            / f"{spans.shot_id}.mp4"
        )
        try:
            GovernedSpanAssemblyRuntime(self.project_directory).assemble(
                raw,
                tuple(span_outputs),
                destination,
            )
        except GovernedSpanAssemblyRuntimeError as exc:
            raise AutomatedTimedSpanOrchestrationError(str(exc)) from exc

        self._record_automatic_qc(raw, spans, requirements, tuple(span_outputs))
        status = self.evaluator.evaluate(raw)
        if status.state is not TimedSpanAcceptanceState.ACCEPTED:
            raise AutomatedTimedSpanOrchestrationError(
                f"Automated span orchestration completed media work but acceptance is "
                f"{status.state.value}: {status.message}"
            )
        return AutomatedTimedSpanOrchestrationResult(
            shot_id=spans.shot_id,
            state=status.state,
            span_outputs=tuple(span_outputs),
            assembled_output=Path(destination).resolve(strict=False),
            message="Automated timed-span orchestration completed and passed governed acceptance.",
        )

    def _synthesis_request(
        self,
        raw: dict[str, Any],
        activation: TimedCanonicalReferenceActivationPlan,
        requirement: IntroductionKeyframeRequirement,
        source_frame: Path,
        working: Path,
    ) -> IntroductionBoundarySynthesisRequest:
        activation_by_span = {item.span_id: item for item in activation.activations}
        active = activation_by_span.get(requirement.target_span_id)
        if active is None:
            raise AutomatedTimedSpanOrchestrationError(
                f"No timed reference activation exists for {requirement.target_span_id}"
            )
        reference_paths = self._reference_paths(raw, requirement.introduced_reference_ids)
        manifest_path = working / "reference_paths.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "introduced_reference_ids": list(requirement.introduced_reference_ids),
                    "introduced_reference_paths": [str(path) for path in reference_paths],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        positive, negative = IntroductionBoundaryAutomationPlanner.prompt(requirement)
        return IntroductionBoundarySynthesisRequest(
            shot_id=requirement.shot_id,
            requirement_id=requirement.requirement_id,
            boundary_id=requirement.boundary_id,
            source_global_frame_index=requirement.source_global_frame_index,
            target_global_frame_index=requirement.target_global_frame_index,
            source_boundary_image_path=source_frame,
            introduced_asset_ids=requirement.introduced_asset_ids,
            introduced_reference_ids=requirement.introduced_reference_ids,
            active_asset_ids=requirement.active_asset_ids,
            active_reference_ids=requirement.active_reference_ids,
            frame_state_reference_ids=activation.frame_state_reference_ids,
            width=self._positive_int(raw.get("width"), "width"),
            height=self._positive_int(raw.get("height"), "height"),
            prompt=positive,
            negative_prompt=negative,
        )

    def _reference_paths(
        self,
        raw: dict[str, Any],
        reference_ids: tuple[str, ...],
    ) -> tuple[Path, ...]:
        reference_plan = raw.get("reference_plan")
        if not isinstance(reference_plan, dict):
            raise AutomatedTimedSpanOrchestrationError(
                "Compiled package has no governed ReferencePlan for boundary synthesis"
            )
        references = reference_plan.get("references")
        if not isinstance(references, list):
            raise AutomatedTimedSpanOrchestrationError(
                "Governed ReferencePlan references must be an array"
            )
        by_id = {
            str(item.get("reference_id") or ""): item
            for item in references
            if isinstance(item, dict)
        }
        paths: list[Path] = []
        for reference_id in reference_ids:
            item = by_id.get(reference_id)
            if item is None:
                raise AutomatedTimedSpanOrchestrationError(
                    f"Governed introduced reference is missing: {reference_id}"
                )
            source = Path(str(item.get("source_path") or "")).expanduser()
            if not source.is_absolute():
                source = self.project_directory / source
            source = source.resolve(strict=False)
            if not source.is_file():
                raise AutomatedTimedSpanOrchestrationError(
                    f"Governed introduced reference image does not exist: {source}"
                )
            paths.append(source)
        return tuple(paths)

    def _register_automated_keyframe(
        self,
        requirement: IntroductionKeyframeRequirement,
        source_frame: Path,
        target_frame: Path,
        automation_record: Path,
    ) -> None:
        source = source_frame.resolve(strict=True)
        target = Path(target_frame).resolve(strict=True)
        if not source.is_relative_to(self.project_directory) or not target.is_relative_to(
            self.project_directory
        ):
            raise AutomatedTimedSpanOrchestrationError(
                "Automated boundary evidence must remain inside the VSCS project"
            )
        record = self.keyframes.create_record(
            requirement,
            image_path=target.relative_to(self.project_directory).as_posix(),
            image_sha256=self._sha256(target),
            source_boundary_image_path=source.relative_to(self.project_directory).as_posix(),
            source_boundary_image_sha256=self._sha256(source),
            approved_by=self.AUTOMATION_ACTOR,
            approved_at=datetime.now(UTC).isoformat(),
            approval_mode="automated_validated",
            automation_record_path=automation_record.relative_to(
                self.project_directory
            ).as_posix(),
        )
        try:
            self.keyframes.save(record, requirement)
        except GovernedIntroductionKeyframeError as exc:
            raise AutomatedTimedSpanOrchestrationError(str(exc)) from exc

    def _record_automatic_qc(
        self,
        raw: dict[str, Any],
        spans: GovernedInternalRenderSpanPlan,
        requirements: IntroductionKeyframeRequirementPlan,
        span_outputs: tuple[Path, ...],
    ) -> None:
        by_span = {
            span.span_id: output
            for span, output in zip(spans.spans, span_outputs, strict=True)
        }
        for requirement in requirements.requirements:
            source_span = next(
                item for item in spans.spans if item.span_id == requirement.source_span_id
            )
            target_span = next(
                item for item in spans.spans if item.span_id == requirement.target_span_id
            )
            working = self._working_directory(requirement)
            source_frame = working / "qc-source.png"
            target_frame = working / "qc-target.png"
            self._extract_frame(
                by_span[source_span.span_id],
                frame_index=source_span.frame_count - 1,
                destination=source_frame,
            )
            self._extract_frame(
                by_span[target_span.span_id],
                frame_index=0,
                destination=target_frame,
            )
            activation_raw = raw.get("timed_reference_activation")
            if not isinstance(activation_raw, dict):
                raise AutomatedTimedSpanOrchestrationError(
                    "Timed reference activation is missing during automatic QC"
                )
            activation = TimedCanonicalReferenceActivationPlan.from_dict(activation_raw)
            request = self._synthesis_request(
                raw,
                activation,
                requirement,
                source_frame,
                working,
            )
            actual = type("_ActualBoundaryResult", (), {
                "image_path": target_frame,
                "provider_id": self.executor.provider_id,
                "provider_job_id": "rendered-span-first-frame",
                "request_fingerprint": request.fingerprint,
                "output_sha256": self._sha256(target_frame),
            })()
            validation = self.validator.validate(request, actual)
            if not validation.passed:
                raise AutomatedTimedSpanOrchestrationError(
                    "Automatic final boundary QC failed: " + ", ".join(validation.findings)
                )
            qc = self.evaluator.make_qc_record(
                requirement,
                absent_before_boundary=True,
                present_from_target_frame=True,
                source_continuity_preserved=True,
                no_unapproved_assets=True,
                approved_by=self.AUTOMATION_ACTOR,
                notes=(
                    "Phase 20.18.2.3.6 automated visual boundary validation: "
                    + validation.validator_id
                ),
            )
            try:
                self.acceptance.save_qc(qc)
            except TimedSpanAcceptanceError as exc:
                raise AutomatedTimedSpanOrchestrationError(str(exc)) from exc

    def _authority(
        self,
        raw: dict[str, Any],
    ) -> tuple[
        GovernedInternalRenderSpanPlan,
        TimedCanonicalReferenceActivationPlan,
        IntroductionKeyframeRequirementPlan,
    ]:
        timed_raw = raw.get("timed_asset_presence")
        spans_raw = raw.get("internal_render_spans")
        activation_raw = raw.get("timed_reference_activation")
        requirements_raw = raw.get("introduction_keyframe_requirements")
        if not all(
            isinstance(value, dict)
            for value in (timed_raw, spans_raw, activation_raw, requirements_raw)
        ):
            raise AutomatedTimedSpanOrchestrationError(
                "Compiled package lacks complete dynamic timed-span authority"
            )
        try:
            timed = TimedAssetPresencePlan.from_dict(timed_raw)
            spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
            activation = TimedCanonicalReferenceActivationPlan.from_dict(activation_raw)
            requirements = IntroductionKeyframeRequirementPlan.from_dict(requirements_raw)
            spans.require_source(timed)
            activation.require_sources(timed, spans, raw.get("reference_plan"))
            requirements.require_sources(spans, activation)
        except (
            TimedAssetPresenceError,
            GovernedInternalRenderSpanError,
            TimedCanonicalReferenceActivationError,
            GovernedIntroductionKeyframeError,
        ) as exc:
            raise AutomatedTimedSpanOrchestrationError(
                f"Dynamic timed-span authority is invalid: {exc}"
            ) from exc
        if spans.span_count <= 1:
            raise AutomatedTimedSpanOrchestrationError(
                "Automated timed-span orchestration applies only to dynamic multi-span Shots"
            )
        return spans, activation, requirements

    def _extract_frame(
        self,
        video: Path,
        *,
        frame_index: int,
        destination: Path,
    ) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = (
            self.ffmpeg,
            "-v",
            "error",
            "-i",
            str(Path(video).resolve(strict=True)),
            "-vf",
            f"select=eq(n\\,{frame_index})",
            "-vsync",
            "0",
            "-frames:v",
            "1",
            "-y",
            str(destination),
        )
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise AutomatedTimedSpanOrchestrationError(
                f"Could not extract governed internal boundary frame {frame_index}: {exc}"
            ) from exc
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise AutomatedTimedSpanOrchestrationError(
                f"Boundary extraction produced no image: {destination}"
            )

    def _working_directory(self, requirement: IntroductionKeyframeRequirement) -> Path:
        path = (
            self.project_directory
            / ".vscs"
            / "automated_introduction_boundaries"
            / requirement.shot_id
            / requirement.requirement_id
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_automation_record(
        self,
        requirement: IntroductionKeyframeRequirement,
        request: IntroductionBoundarySynthesisRequest,
        *,
        synthesis: Any | None,
        validation: Any | None,
        state: str,
        findings: tuple[str, ...],
    ) -> Path:
        directory = self._working_directory(requirement)
        path = directory / "automation.json"
        payload = {
            "schema_version": "1.0",
            "phase": "20.18.2.3.6",
            "shot_id": requirement.shot_id,
            "requirement_id": requirement.requirement_id,
            "boundary_id": requirement.boundary_id,
            "state": state,
            "recorded_at": datetime.now(UTC).isoformat(),
            "request_fingerprint": request.fingerprint,
            "source_boundary_image_path": str(request.source_boundary_image_path),
            "source_boundary_image_sha256": self._sha256(request.source_boundary_image_path),
            "introduced_asset_ids": list(request.introduced_asset_ids),
            "introduced_reference_ids": list(request.introduced_reference_ids),
            "synthesis": (
                {
                    "provider_id": synthesis.provider_id,
                    "provider_job_id": synthesis.provider_job_id,
                    "image_path": str(synthesis.image_path),
                    "output_sha256": synthesis.output_sha256,
                }
                if synthesis is not None
                else None
            ),
            "validation": (
                {
                    "passed": validation.passed,
                    "validator_id": validation.validator_id,
                    "checks": list(validation.checks),
                    "findings": list(validation.findings),
                }
                if validation is not None
                else None
            ),
            "findings": list(findings),
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise AutomatedTimedSpanOrchestrationError(
                f"Compiled Production Package does not exist: {path}"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedTimedSpanOrchestrationError(
                f"Cannot read compiled Production Package: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise AutomatedTimedSpanOrchestrationError(
                "Compiled Production Package root must be an object"
            )
        return raw

    @staticmethod
    def _positive_int(value: object, field_name: str) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        raise AutomatedTimedSpanOrchestrationError(
            f"Compiled Production Package {field_name} must be a positive integer"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
