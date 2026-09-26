"""Automated internal-span orchestration for Phase 20.18.2.3.6."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from vscs.application.production_execution.automated_introduction_boundary import (
    AutomatedBoundaryValidationState,
    AutomatedIntroductionBoundaryRequest,
    AutomatedIntroductionBoundaryResult,
    AutomatedIntroductionBoundaryStore,
    file_sha256,
    request_from_requirement,
)
from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.introduction_keyframes import (
    GovernedIntroductionKeyframeError,
    GovernedIntroductionKeyframeStore,
    IntroductionKeyframeRequirement,
    IntroductionKeyframeRequirementPlan,
)
from vscs.application.production_execution.timed_span_acceptance import (
    TimedSpanAcceptanceState,
    TimedSpanAcceptanceStatus,
)
from vscs.application.timed_asset_presence import TimedAssetPresencePlan

from .timed_span_acceptance_packages import (
    LTX25TimedSpanAcceptancePackageBuilder,
    TimedSpanAcceptancePackageError,
)
from .timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    GovernedSpanAssemblyRuntimeError,
)
from .timed_span_acceptance_service import TimedSpanFunctionalAcceptanceService


class AutomatedSpanOrchestrationError(RuntimeError):
    """Raised when automated span synthesis or execution cannot continue safely."""


class SpanVideoProvider(Protocol):
    def render(self, package_path: Path) -> Path: ...

    def free_models_and_memory(self) -> None: ...


class IntroductionBoundarySynthesizer(Protocol):
    def preflight(self) -> None: ...

    def synthesize(
        self,
        request: AutomatedIntroductionBoundaryRequest,
    ) -> AutomatedIntroductionBoundaryResult: ...


@dataclass(frozen=True, slots=True)
class AutomatedSpanOrchestrationResult:
    """Final orchestration result for one editorial Shot."""

    shot_id: str
    task_id: str
    span_paths: tuple[Path, ...]
    synthesized_keyframe_ids: tuple[str, ...]
    final_path: Path
    acceptance_status: TimedSpanAcceptanceStatus

    @property
    def completed_provider_work(self) -> bool:
        return (
            bool(self.span_paths)
            and self.final_path.is_file()
            and self.acceptance_status.state
            in {
                TimedSpanAcceptanceState.QC_REQUIRED,
                TimedSpanAcceptanceState.ACCEPTED,
            }
        )


class GovernedInternalBoundaryFrameExtractor:
    """Decode the exact final governed frame of a normalized internal span."""

    def __init__(self, project_directory: Path, *, ffmpeg: str = "ffmpeg") -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.ffmpeg = ffmpeg

    def extract(
        self,
        span_path: Path,
        *,
        local_frame_index: int,
        shot_id: str,
        requirement_id: str,
        global_frame_index: int,
    ) -> Path:
        if local_frame_index < 0 or global_frame_index < 0:
            raise AutomatedSpanOrchestrationError(
                "Internal boundary frame indices cannot be negative"
            )
        source = Path(span_path).expanduser().resolve(strict=False)
        if not source.is_file():
            raise AutomatedSpanOrchestrationError(
                f"Normalized source span does not exist: {source}"
            )
        destination = (
            self.project_directory
            / ".vscs"
            / "automated_introduction_boundaries"
            / shot_id.strip().upper()
            / requirement_id
            / f"source-frame-{global_frame_index:06d}.png"
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = (
            self.ffmpeg,
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-vf",
            f"select=eq(n\,{local_frame_index})",
            "-vsync",
            "0",
            "-frames:v",
            "1",
            str(destination),
        )
        try:
            subprocess.run(command, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise AutomatedSpanOrchestrationError(
                f"Unable to extract exact governed boundary frame: {exc}"
            ) from exc
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise AutomatedSpanOrchestrationError(
                "Provider span completed but exact boundary-frame extraction produced no image"
            )
        return destination


class AutomatedTimedSpanOrchestrationService:
    """Render spans, synthesize introduced assets, assemble, then hand off final visual QC."""

    def __init__(
        self,
        project_directory: Path,
        *,
        span_provider: SpanVideoProvider,
        synthesizer: IntroductionBoundarySynthesizer,
        extractor: GovernedInternalBoundaryFrameExtractor | None = None,
        assembly_runtime: GovernedSpanAssemblyRuntime | None = None,
        managed_media_directory: str | Path = "Media Output",
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.span_provider = span_provider
        self.synthesizer = synthesizer
        self.extractor = extractor or GovernedInternalBoundaryFrameExtractor(self.project_directory)
        self.assembly_runtime = assembly_runtime or GovernedSpanAssemblyRuntime(
            self.project_directory
        )
        self.managed_media_directory = Path(managed_media_directory)
        self.keyframes = GovernedIntroductionKeyframeStore(self.project_directory)
        self.boundaries = AutomatedIntroductionBoundaryStore(self.project_directory)
        self.packages = LTX25TimedSpanAcceptancePackageBuilder(self.project_directory)
        self.acceptance = TimedSpanFunctionalAcceptanceService(self.project_directory)

    def run(self, compiled_package_path: Path) -> AutomatedSpanOrchestrationResult:
        package_path = Path(compiled_package_path).expanduser().resolve(strict=False)
        raw = self._read_package(package_path)
        manifest = raw.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise AutomatedSpanOrchestrationError(
                "Compiled Production Package has no VSCS manifest"
            )
        task_id = str(manifest.get("task_id") or "").strip()
        package_fingerprint = str(manifest.get("package_fingerprint") or "").strip().lower()
        if not task_id or not package_fingerprint:
            raise AutomatedSpanOrchestrationError(
                "Compiled Production Package identity is incomplete"
            )

        timed_raw = raw.get("timed_asset_presence")
        spans_raw = raw.get("internal_render_spans")
        requirements_raw = raw.get("introduction_keyframe_requirements")
        if not isinstance(timed_raw, dict) or not isinstance(spans_raw, dict):
            raise AutomatedSpanOrchestrationError(
                "Automated orchestration requires governed timed-span authority"
            )
        if not isinstance(requirements_raw, dict):
            raise AutomatedSpanOrchestrationError(
                "Automated orchestration requires Introduction Keyframe requirements"
            )
        timed = TimedAssetPresencePlan.from_dict(timed_raw)
        spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
        requirements = IntroductionKeyframeRequirementPlan.from_dict(requirements_raw)
        if spans.span_count <= 1:
            raise AutomatedSpanOrchestrationError(
                "Monolithic Shots do not require automated timed-span orchestration"
            )
        if requirements.requirement_count != spans.span_count - 1:
            raise AutomatedSpanOrchestrationError(
                "Automated orchestration requires exactly one introduction requirement "
                "for every non-initial span"
            )
        reference_plan = self._reference_plan(raw)
        try:
            self.synthesizer.preflight()
        except Exception as exc:
            raise AutomatedSpanOrchestrationError(
                f"Automated Introduction Keyframe provider is not ready: {exc}"
            ) from exc

        resume = self._load_resume_state(task_id, package_fingerprint)
        span_outputs: list[Path] = []
        synthesized_ids: list[str] = []
        for sequence_number, span in enumerate(spans.spans, start=1):
            try:
                package_set = self.packages.build(
                    package_path,
                    through_sequence=sequence_number,
                )
            except TimedSpanAcceptancePackageError as exc:
                raise AutomatedSpanOrchestrationError(str(exc)) from exc
            span_package = package_set.package_paths[-1]
            span_package_sha256 = file_sha256(span_package)
            span_output = self._reusable_span_output(
                resume,
                sequence_number=sequence_number,
                span_id=span.span_id,
                span_package_sha256=span_package_sha256,
            )
            if span_output is None:
                try:
                    span_output = Path(self.span_provider.render(span_package)).resolve(
                        strict=False
                    )
                except Exception as exc:
                    raise AutomatedSpanOrchestrationError(
                        f"Provider execution failed for governed span {sequence_number}: {exc}"
                    ) from exc
                output_sha256 = file_sha256(span_output)
                self._record_span_resume(
                    resume,
                    sequence_number=sequence_number,
                    span_id=span.span_id,
                    span_package_path=span_package,
                    span_package_sha256=span_package_sha256,
                    output_path=span_output,
                    output_sha256=output_sha256,
                )
                self._save_resume_state(task_id, package_fingerprint, resume)
                event_name = "span_completed"
            else:
                output_sha256 = file_sha256(span_output)
                event_name = "span_reused"
            span_outputs.append(span_output)
            self._audit(
                task_id,
                {
                    "event": event_name,
                    "sequence_number": sequence_number,
                    "span_id": span.span_id,
                    "package_path": str(span_package),
                    "package_sha256": span_package_sha256,
                    "output_path": str(span_output),
                    "output_sha256": output_sha256,
                },
            )
            if sequence_number >= spans.span_count:
                continue

            requirement = self._requirement_for_source_span(
                requirements,
                span.span_id,
            )
            boundary_image = self.extractor.extract(
                span_output,
                local_frame_index=span.frame_count - 1,
                shot_id=spans.shot_id,
                requirement_id=requirement.requirement_id,
                global_frame_index=requirement.source_global_frame_index,
            )
            boundary_sha256 = file_sha256(boundary_image)
            if self._has_current_keyframe_for_boundary(requirement, boundary_sha256):
                continue

            self._release_provider_memory()
            request = request_from_requirement(
                requirement,
                source_boundary_image_path=boundary_image,
                source_boundary_image_sha256=boundary_sha256,
                reference_plan=reference_plan,
                timed_asset_presence=timed_raw,
                width=int(raw.get("width") or 0),
                height=int(raw.get("height") or 0),
                source_package_fingerprint=package_fingerprint,
                seed=int(raw.get("seed") or 0) + requirement.target_global_frame_index,
            )
            self.boundaries.save_request(request)
            try:
                result = self.synthesizer.synthesize(request)
            except Exception as exc:
                raise AutomatedSpanOrchestrationError(
                    f"Automated Introduction Keyframe synthesis failed safely: {exc}"
                ) from exc
            self.boundaries.save_result(result)
            if result.validation_state is not AutomatedBoundaryValidationState.PASSED:
                raise AutomatedSpanOrchestrationError(
                    "Automated introduction-boundary synthesis requires human review before "
                    f"continuing: {', '.join(result.validation_findings)}"
                )
            self._register_automated_keyframe(requirement, result)
            synthesized = self.keyframes.require_approved(requirement)
            synthesized_ids.append(synthesized.keyframe_id)
            self._audit(
                task_id,
                {
                    "event": "introduction_boundary_synthesized",
                    "requirement_id": requirement.requirement_id,
                    "keyframe_id": synthesized.keyframe_id,
                    "target_global_frame_index": requirement.target_global_frame_index,
                    "image_path": str(self.keyframes.image_path(synthesized)),
                    "image_sha256": synthesized.image_sha256,
                    "provider": result.provider_name,
                    "model": result.model,
                },
            )
            self._release_provider_memory()

        output_path = self._final_output_path(spans.shot_id, task_id)
        try:
            self.assembly_runtime.assemble(
                raw,
                tuple(span_outputs),
                output_path,
            )
        except GovernedSpanAssemblyRuntimeError as exc:
            raise AutomatedSpanOrchestrationError(str(exc)) from exc
        status = self.acceptance.status(package_path)
        if status.state not in {
            TimedSpanAcceptanceState.QC_REQUIRED,
            TimedSpanAcceptanceState.ACCEPTED,
        }:
            raise AutomatedSpanOrchestrationError(
                "Automated span provider work completed but acceptance state is "
                f"{status.state.value}: {status.message}"
            )
        self._audit(
            task_id,
            {
                "event": "assembly_completed",
                "shot_id": spans.shot_id,
                "final_path": str(output_path),
                "final_sha256": file_sha256(output_path),
                "acceptance_state": status.state.value,
            },
        )
        return AutomatedSpanOrchestrationResult(
            shot_id=spans.shot_id,
            task_id=task_id,
            span_paths=tuple(span_outputs),
            synthesized_keyframe_ids=tuple(synthesized_ids),
            final_path=output_path,
            acceptance_status=status,
        )

    def _register_automated_keyframe(
        self,
        requirement: IntroductionKeyframeRequirement,
        result: AutomatedIntroductionBoundaryResult,
    ) -> None:
        image = self._project_file(result.image_path, "synthesized Introduction Keyframe")
        source = self._project_file(
            result.source_boundary_image_path,
            "automatically extracted source boundary",
        )
        record = self.keyframes.create_record(
            requirement,
            image_path=image.relative_to(self.project_directory).as_posix(),
            image_sha256=result.image_sha256,
            source_boundary_image_path=source.relative_to(self.project_directory).as_posix(),
            source_boundary_image_sha256=result.source_boundary_image_sha256,
            approved_by=f"VSCS Automation — {result.provider_name}",
            approved_at=result.generated_at,
            acceptance_criteria=(
                "source_boundary_continuity_preserved",
                "target_span_first_emitted_frame_correct",
            ),
            approval_mode="automated_structural",
            automated_validation_findings=result.validation_findings,
        )
        try:
            self.keyframes.save(record, requirement)
        except GovernedIntroductionKeyframeError as exc:
            raise AutomatedSpanOrchestrationError(
                f"Cannot register automated Introduction Keyframe: {exc}"
            ) from exc

    def _has_current_keyframe_for_boundary(
        self,
        requirement: IntroductionKeyframeRequirement,
        source_boundary_sha256: str,
    ) -> bool:
        try:
            current = self.keyframes.require_approved(requirement)
        except GovernedIntroductionKeyframeError:
            return False
        return current.source_boundary_image_sha256 == source_boundary_sha256.strip().lower()

    def _resume_state_path(self) -> Path:
        return self.project_directory / ".vscs" / "automated_span_orchestration_state.json"

    def _load_resume_state(
        self,
        task_id: str,
        package_fingerprint: str,
    ) -> dict[str, Any]:
        path = self._resume_state_path()
        if not path.is_file():
            return {"spans": {}}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {"spans": {}}
        if not isinstance(raw, dict):
            return {"spans": {}}
        tasks = raw.get("tasks")
        if not isinstance(tasks, dict):
            return {"spans": {}}
        current = tasks.get(task_id)
        if not isinstance(current, dict):
            return {"spans": {}}
        if str(current.get("package_fingerprint") or "").strip().lower() != package_fingerprint:
            return {"spans": {}}
        spans = current.get("spans")
        if not isinstance(spans, dict):
            return {"spans": {}}
        return {"spans": dict(spans)}

    def _save_resume_state(
        self,
        task_id: str,
        package_fingerprint: str,
        state: dict[str, Any],
    ) -> None:
        path = self._resume_state_path()
        raw: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                raw = loaded
        tasks = raw.get("tasks")
        if not isinstance(tasks, dict):
            tasks = {}
        tasks[task_id] = {
            "package_fingerprint": package_fingerprint,
            "spans": dict(state.get("spans") or {}),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        output = {"schema_version": "1.0", "tasks": tasks}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _reusable_span_output(
        self,
        state: dict[str, Any],
        *,
        sequence_number: int,
        span_id: str,
        span_package_sha256: str,
    ) -> Path | None:
        spans = state.get("spans")
        if not isinstance(spans, dict):
            return None
        record = spans.get(str(sequence_number))
        if not isinstance(record, dict):
            return None
        if str(record.get("span_id") or "") != span_id:
            return None
        if (
            str(record.get("span_package_sha256") or "").strip().lower()
            != span_package_sha256.strip().lower()
        ):
            return None
        output_value = str(record.get("output_path") or "").strip()
        expected_sha = str(record.get("output_sha256") or "").strip().lower()
        if not output_value or not expected_sha:
            return None
        output = Path(output_value).expanduser().resolve(strict=False)
        if not output.is_file():
            return None
        try:
            actual_sha = file_sha256(output)
        except OSError:
            return None
        if actual_sha != expected_sha:
            return None
        return output

    @staticmethod
    def _record_span_resume(
        state: dict[str, Any],
        *,
        sequence_number: int,
        span_id: str,
        span_package_path: Path,
        span_package_sha256: str,
        output_path: Path,
        output_sha256: str,
    ) -> None:
        spans = state.get("spans")
        if not isinstance(spans, dict):
            spans = {}
            state["spans"] = spans
        spans[str(sequence_number)] = {
            "span_id": span_id,
            "span_package_path": str(span_package_path),
            "span_package_sha256": span_package_sha256,
            "output_path": str(output_path),
            "output_sha256": output_sha256,
        }

    @staticmethod
    def _requirement_for_source_span(
        requirements: IntroductionKeyframeRequirementPlan,
        source_span_id: str,
    ) -> IntroductionKeyframeRequirement:
        match = next(
            (item for item in requirements.requirements if item.source_span_id == source_span_id),
            None,
        )
        if match is None:
            raise AutomatedSpanOrchestrationError(
                f"No Introduction Keyframe requirement follows source span {source_span_id}"
            )
        return match

    @staticmethod
    def _reference_plan(raw: dict[str, Any]) -> dict[str, Any]:
        direct = raw.get("reference_plan")
        if isinstance(direct, dict):
            return direct
        composition = raw.get("composition_plan")
        if isinstance(composition, dict):
            nested = composition.get("reference_plan")
            if isinstance(nested, dict):
                return nested
        raise AutomatedSpanOrchestrationError(
            "Compiled Production Package has no governed ReferencePlan for synthesis"
        )

    def _final_output_path(self, shot_id: str, task_id: str) -> Path:
        root = self.managed_media_directory
        if not root.is_absolute():
            root = self.project_directory / root
        root = root.resolve(strict=False)
        if not root.is_relative_to(self.project_directory):
            raise AutomatedSpanOrchestrationError(
                "Managed automated-span output directory must remain inside the VSCS project"
            )
        destination = root / "Automated Spans" / shot_id / f"{task_id}-assembled.mp4"
        destination.parent.mkdir(parents=True, exist_ok=True)
        return destination

    def _project_file(self, value: str, label: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.project_directory):
            raise AutomatedSpanOrchestrationError(f"{label} must remain inside the VSCS project")
        if not resolved.is_file():
            raise AutomatedSpanOrchestrationError(f"{label} does not exist: {resolved}")
        return resolved

    def _release_provider_memory(self) -> None:
        try:
            self.span_provider.free_models_and_memory()
        except Exception:
            pass

    def _audit(self, task_id: str, event: dict[str, Any]) -> None:
        path = self.project_directory / ".vscs" / "automated_span_orchestration.json"
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                raw = {}
        else:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        events = [dict(item) for item in raw.get("events", []) if isinstance(item, dict)]
        events.append(
            {
                "task_id": task_id,
                "recorded_at": datetime.now(UTC).isoformat(),
                **event,
            }
        )
        output = {"schema_version": "1.0", "events": events}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _read_package(path: Path) -> dict[str, Any]:
        candidate = Path(path).expanduser().resolve(strict=False)
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedSpanOrchestrationError(
                f"Cannot read compiled Production Package: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise AutomatedSpanOrchestrationError(
                "Compiled Production Package root must be an object"
            )
        return raw
