"""Governed MiniMax H3 span orchestration and assembly for Phase 20.18.2.3.6.4d."""

from __future__ import annotations

import json
import subprocess
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from vscs.application.production_execution.package_compilation import CompiledProductionPackage

from .minimax_h3_span_adapter import (
    MiniMaxH3SpanAdapterCompiler,
    MiniMaxH3SpanAdapterError,
    MiniMaxH3SpanExecution,
    MiniMaxH3SpanExecutionPlan,
)
from .timed_span_acceptance_runtime import (
    GovernedSpanAssemblyRuntime,
    GovernedSpanAssemblyRuntimeError,
)


class MiniMaxH3SpanOrchestrationError(RuntimeError):
    """Raised when governed H3 span execution, normalization, or assembly fails."""


class MiniMaxH3SpanProvider(Protocol):
    """Provider boundary for exactly one isolated H3 span job."""

    def render(self, execution: MiniMaxH3SpanExecution) -> Path: ...

    def free_models_and_memory(self) -> None: ...


class MiniMaxH3SpanNormalizer(Protocol):
    """Normalize one provider-native H3 output to its governed frame interval."""

    def normalize(
        self,
        source_path: Path,
        destination_path: Path,
        *,
        provider_frame_count: int,
        governed_frame_count: int,
        frames_per_second: int,
    ) -> Path: ...


class MiniMaxH3SpanAssembler(Protocol):
    """Assemble already-normalized spans into the editorial Shot."""

    def assemble(
        self,
        compiled_package: dict[str, Any],
        span_paths: tuple[Path, ...],
        output_path: Path,
    ) -> Any: ...


@dataclass(frozen=True, slots=True)
class MiniMaxH3SpanOrchestrationResult:
    """Completed governed H3 multi-span execution."""

    shot_id: str
    task_id: str
    plan_id: str
    plan_fingerprint: str
    raw_span_paths: tuple[Path, ...]
    normalized_span_paths: tuple[Path, ...]
    final_path: Path

    def __post_init__(self) -> None:
        if not self.shot_id.strip() or not self.task_id.strip():
            raise MiniMaxH3SpanOrchestrationError(
                "H3 orchestration result requires Shot and task identity"
            )
        if not self.plan_id.strip() or not self.plan_fingerprint.strip():
            raise MiniMaxH3SpanOrchestrationError(
                "H3 orchestration result requires execution-plan authority"
            )
        if not self.raw_span_paths or len(self.raw_span_paths) != len(self.normalized_span_paths):
            raise MiniMaxH3SpanOrchestrationError(
                "H3 orchestration result requires matching raw and normalized spans"
            )
        if not self.final_path.is_file():
            raise MiniMaxH3SpanOrchestrationError(
                f"H3 assembled Shot does not exist: {self.final_path}"
            )


class FFmpegMiniMaxH3SpanNormalizer:
    """Trim an H3-native render to exactly the governed leading frame interval."""

    def __init__(
        self,
        project_directory: Path,
        *,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe

    def normalize(
        self,
        source_path: Path,
        destination_path: Path,
        *,
        provider_frame_count: int,
        governed_frame_count: int,
        frames_per_second: int,
    ) -> Path:
        if provider_frame_count <= 0 or governed_frame_count <= 0:
            raise MiniMaxH3SpanOrchestrationError("H3 normalization frame counts must be positive")
        if governed_frame_count > provider_frame_count:
            raise MiniMaxH3SpanOrchestrationError(
                "H3 governed frame count cannot exceed provider frame count"
            )
        if frames_per_second <= 0:
            raise MiniMaxH3SpanOrchestrationError("H3 normalization frame rate must be positive")

        source = Path(source_path).expanduser().resolve(strict=False)
        if not source.is_file():
            raise MiniMaxH3SpanOrchestrationError(f"H3 provider output does not exist: {source}")
        observed_source_frames = self._frame_count(source)
        if observed_source_frames != provider_frame_count:
            raise MiniMaxH3SpanOrchestrationError(
                f"H3 provider output has {observed_source_frames} frames; "
                f"execution authority requires exactly {provider_frame_count}."
            )

        destination = Path(destination_path).expanduser()
        if not destination.is_absolute():
            destination = self.project_directory / destination
        destination = destination.resolve(strict=False)
        if not destination.is_relative_to(self.project_directory):
            raise MiniMaxH3SpanOrchestrationError(
                "Normalized H3 spans must be written inside the VSCS project"
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
            f"trim=end_frame={governed_frame_count},setpts=PTS-STARTPTS",
            "-an",
            "-r",
            str(frames_per_second),
            "-frames:v",
            str(governed_frame_count),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(destination),
        )
        try:
            subprocess.run(command, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise MiniMaxH3SpanOrchestrationError(
                f"Unable to normalize H3 span output: {exc}"
            ) from exc

        if not destination.is_file() or destination.stat().st_size <= 0:
            raise MiniMaxH3SpanOrchestrationError("H3 span normalization produced no output")
        observed_normalized_frames = self._frame_count(destination)
        if observed_normalized_frames != governed_frame_count:
            raise MiniMaxH3SpanOrchestrationError(
                f"Normalized H3 span has {observed_normalized_frames} frames; "
                f"governed authority requires exactly {governed_frame_count}."
            )
        return destination

    def _frame_count(self, path: Path) -> int:
        command = (
            self.ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(path),
        )
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            value = completed.stdout.strip()
            frames = int(value)
        except (OSError, subprocess.CalledProcessError, ValueError) as exc:
            raise MiniMaxH3SpanOrchestrationError(
                f"Unable to inspect H3 span frame count: {exc}"
            ) from exc
        if frames <= 0:
            raise MiniMaxH3SpanOrchestrationError(
                f"H3 span has invalid observed frame count: {frames}"
            )
        return frames


class GovernedMiniMaxH3SpanOrchestrationService:
    """Render each governed span as an isolated H3 job, normalize, then assemble."""

    def __init__(
        self,
        project_directory: Path,
        *,
        provider: MiniMaxH3SpanProvider,
        normalizer: MiniMaxH3SpanNormalizer | None = None,
        assembler: MiniMaxH3SpanAssembler | None = None,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.provider = provider
        self.normalizer = normalizer or FFmpegMiniMaxH3SpanNormalizer(self.project_directory)
        self.assembler = assembler or GovernedSpanAssemblyRuntime(self.project_directory)
        self.adapter = MiniMaxH3SpanAdapterCompiler(self.project_directory)

    def run(
        self,
        compiled: CompiledProductionPackage,
        *,
        output_path: Path | None = None,
    ) -> MiniMaxH3SpanOrchestrationResult:
        try:
            plan = self.adapter.compile(compiled)
        except MiniMaxH3SpanAdapterError as exc:
            raise MiniMaxH3SpanOrchestrationError(
                f"H3 span orchestration authority is invalid: {exc}"
            ) from exc

        if plan.governed_frame_count != compiled.frame_count:
            raise MiniMaxH3SpanOrchestrationError(
                "H3 execution plan does not cover the governed Shot exactly"
            )

        root = (
            self.project_directory
            / ".vscs"
            / "h3_span_orchestration"
            / compiled.task_id
            / plan.plan_id
        )
        raw_directory = root / "raw"
        normalized_directory = root / "normalized"
        raw_directory.mkdir(parents=True, exist_ok=True)
        normalized_directory.mkdir(parents=True, exist_ok=True)

        raw_paths: list[Path] = []
        normalized_paths: list[Path] = []
        try:
            for execution in plan.spans:
                raw = Path(self.provider.render(execution)).expanduser().resolve(strict=False)
                if not raw.is_file():
                    raise MiniMaxH3SpanOrchestrationError(
                        f"H3 provider returned a missing span output: {raw}"
                    )
                raw_paths.append(raw)

                normalized_target = (
                    normalized_directory / f"span-{execution.sequence_number:03d}.mp4"
                )
                normalized = self.normalizer.normalize(
                    raw,
                    normalized_target,
                    provider_frame_count=execution.provider_frame_count,
                    governed_frame_count=execution.governed_frame_count,
                    frames_per_second=compiled.frames_per_second,
                )
                normalized = Path(normalized).expanduser().resolve(strict=False)
                if not normalized.is_file():
                    raise MiniMaxH3SpanOrchestrationError(
                        f"H3 normalizer returned a missing span output: {normalized}"
                    )
                normalized_paths.append(normalized)

            final_target = self._final_output_path(
                compiled,
                root,
                output_path,
            )
            try:
                evidence = self.assembler.assemble(
                    compiled.to_dict(),
                    tuple(normalized_paths),
                    final_target,
                )
            except GovernedSpanAssemblyRuntimeError as exc:
                raise MiniMaxH3SpanOrchestrationError(
                    f"Governed H3 span assembly failed: {exc}"
                ) from exc
            final = self._evidence_final_path(evidence, final_target)
            if not final.is_file():
                raise MiniMaxH3SpanOrchestrationError(
                    f"Governed H3 assembly produced no final Shot: {final}"
                )

            self._persist_manifest(
                compiled,
                plan,
                tuple(raw_paths),
                tuple(normalized_paths),
                final,
                root,
            )
            return MiniMaxH3SpanOrchestrationResult(
                shot_id=compiled.shot_id,
                task_id=compiled.task_id,
                plan_id=plan.plan_id,
                plan_fingerprint=plan.fingerprint,
                raw_span_paths=tuple(raw_paths),
                normalized_span_paths=tuple(normalized_paths),
                final_path=final,
            )
        finally:
            with suppress(Exception):
                self.provider.free_models_and_memory()

    def _final_output_path(
        self,
        compiled: CompiledProductionPackage,
        root: Path,
        requested: Path | None,
    ) -> Path:
        candidate = requested or (root / f"{compiled.shot_id}-governed-h3-assembled.mp4")
        candidate = Path(candidate).expanduser()
        if not candidate.is_absolute():
            candidate = self.project_directory / candidate
        candidate = candidate.resolve(strict=False)
        if not candidate.is_relative_to(self.project_directory):
            raise MiniMaxH3SpanOrchestrationError(
                "Final governed H3 Shot must be written inside the VSCS project"
            )
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate

    @staticmethod
    def _evidence_final_path(evidence: Any, fallback: Path) -> Path:
        value = getattr(evidence, "final_path", None)
        if isinstance(value, str) and value.strip():
            return Path(value).expanduser().resolve(strict=False)
        if isinstance(value, Path):
            return value.expanduser().resolve(strict=False)
        return fallback.resolve(strict=False)

    def _persist_manifest(
        self,
        compiled: CompiledProductionPackage,
        plan: MiniMaxH3SpanExecutionPlan,
        raw_paths: tuple[Path, ...],
        normalized_paths: tuple[Path, ...],
        final_path: Path,
        root: Path,
    ) -> None:
        payload = {
            "schema_version": "1.0",
            "provider": plan.provider_id,
            "provider_profile_id": plan.provider_profile_id,
            "provider_profile_fingerprint": plan.provider_profile_fingerprint,
            "execution_adapter_id": plan.execution_adapter_id,
            "mode": plan.mode,
            "shot_id": compiled.shot_id,
            "task_id": compiled.task_id,
            "source_package_fingerprint": compiled.package_fingerprint,
            "plan_id": plan.plan_id,
            "plan_fingerprint": plan.fingerprint,
            "assembly_policy": "concatenate_normalized_span_outputs_in_sequence",
            "spans": [
                {
                    **execution.to_dict(),
                    "raw_output_path": str(raw),
                    "normalized_output_path": str(normalized),
                }
                for execution, raw, normalized in zip(
                    plan.spans,
                    raw_paths,
                    normalized_paths,
                    strict=True,
                )
            ],
            "final_path": str(final_path),
            "final_frame_count": compiled.frame_count,
            "frames_per_second": compiled.frames_per_second,
        }
        destination = root / "orchestration.json"
        destination.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
