"""Normalized span-output verification and assembly for Phase 20.18.2.3.5."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from typing import Any

from vscs.application.production_execution.internal_render_spans import (
    GovernedInternalRenderSpanError,
    GovernedInternalRenderSpanPlan,
)
from vscs.application.production_execution.timed_span_acceptance import (
    TimedSpanAcceptanceError,
    TimedSpanAcceptanceStore,
    TimedSpanAssemblyEvidence,
)


class GovernedSpanAssemblyRuntimeError(RuntimeError):
    """Raised when normalized internal-span outputs cannot be assembled safely."""


@dataclass(frozen=True, slots=True)
class SpanMediaObservation:
    """Observed video facts used to prove one normalized span output."""

    path: Path
    frame_count: int
    width: int
    height: int
    frames_per_second: int

    def __post_init__(self) -> None:
        if self.frame_count <= 0:
            raise GovernedSpanAssemblyRuntimeError("Observed span frame count must be positive")
        if self.width <= 0 or self.height <= 0 or self.frames_per_second <= 0:
            raise GovernedSpanAssemblyRuntimeError(
                "Observed span dimensions and frame rate must be positive"
            )


class GovernedSpanAssemblyRuntime:
    """Verify normalized span outputs, concatenate them, and persist acceptance evidence."""

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
        self.acceptance = TimedSpanAcceptanceStore(self.project_directory)

    def assemble(
        self,
        compiled_package: dict[str, Any],
        span_paths: tuple[Path, ...],
        output_path: Path,
    ) -> TimedSpanAssemblyEvidence:
        spans_raw = compiled_package.get("internal_render_spans")
        if not isinstance(spans_raw, dict):
            raise GovernedSpanAssemblyRuntimeError(
                "Compiled package has no governed internal render-span authority"
            )
        try:
            spans = GovernedInternalRenderSpanPlan.from_dict(spans_raw)
        except GovernedInternalRenderSpanError as exc:
            raise GovernedSpanAssemblyRuntimeError(
                f"Governed internal render-span authority is invalid: {exc}"
            ) from exc
        if spans.span_count <= 1:
            raise GovernedSpanAssemblyRuntimeError(
                "Monolithic Shots do not require internal-span assembly"
            )
        if len(span_paths) != spans.span_count:
            raise GovernedSpanAssemblyRuntimeError(
                f"Expected {spans.span_count} normalized span outputs, got {len(span_paths)}"
            )

        observations = tuple(self._observe(Path(path)) for path in span_paths)
        for span, observation in zip(spans.spans, observations, strict=True):
            if observation.frame_count != span.frame_count:
                raise GovernedSpanAssemblyRuntimeError(
                    f"Span {span.sequence_number} normalized output has "
                    f"{observation.frame_count} frames; governed authority requires "
                    f"{span.frame_count}."
                )
            if observation.frames_per_second != spans.frames_per_second:
                raise GovernedSpanAssemblyRuntimeError(
                    f"Span {span.sequence_number} frame rate does not match governed "
                    f"{spans.frames_per_second} fps."
                )

        first = observations[0]
        for observation in observations[1:]:
            if (observation.width, observation.height) != (first.width, first.height):
                raise GovernedSpanAssemblyRuntimeError(
                    "Normalized span outputs have inconsistent dimensions"
                )

        destination = Path(output_path).expanduser()
        if not destination.is_absolute():
            destination = self.project_directory / destination
        destination = destination.resolve(strict=False)
        if not destination.is_relative_to(self.project_directory):
            raise GovernedSpanAssemblyRuntimeError(
                "Final assembled Shot must be written inside the VSCS project"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._assemble(tuple(observation.path for observation in observations), destination)
        final = self._observe(destination)

        expected_frames = sum(span.frame_count for span in spans.spans)
        if expected_frames != spans.frame_count:
            raise GovernedSpanAssemblyRuntimeError(
                "Governed span topology does not sum to the Shot frame count"
            )
        if final.frame_count != spans.frame_count:
            raise GovernedSpanAssemblyRuntimeError(
                f"Final assembled Shot has {final.frame_count} frames; governed authority "
                f"requires exactly {spans.frame_count}."
            )
        if (final.width, final.height) != (first.width, first.height):
            raise GovernedSpanAssemblyRuntimeError(
                "Final assembled Shot dimensions changed during assembly"
            )
        if final.frames_per_second != spans.frames_per_second:
            raise GovernedSpanAssemblyRuntimeError(
                "Final assembled Shot frame rate changed during assembly"
            )

        evidence = TimedSpanAssemblyEvidence(
            shot_id=spans.shot_id,
            source_span_plan_id=spans.plan_id,
            source_span_plan_fingerprint=spans.fingerprint,
            span_ids=tuple(span.span_id for span in spans.spans),
            span_paths=tuple(str(observation.path) for observation in observations),
            span_frame_counts=tuple(observation.frame_count for observation in observations),
            final_path=str(destination),
            final_frame_count=final.frame_count,
            width=final.width,
            height=final.height,
            frames_per_second=final.frames_per_second,
            final_sha256=self._sha256(destination),
            recorded_at=datetime.now(UTC).isoformat(),
        )
        try:
            return self.acceptance.save_assembly(evidence)
        except TimedSpanAcceptanceError as exc:
            raise GovernedSpanAssemblyRuntimeError(
                f"Cannot persist timed-span assembly evidence: {exc}"
            ) from exc

    def _observe(self, path: Path) -> SpanMediaObservation:
        candidate = Path(path).expanduser().resolve(strict=False)
        if not candidate.is_file():
            raise GovernedSpanAssemblyRuntimeError(f"Span video does not exist: {candidate}")
        command = (
            self.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=width,height,r_frame_rate,nb_read_frames,nb_frames",
            "-of",
            "json",
            str(candidate),
        )
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
            raw = json.loads(completed.stdout)
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
            raise GovernedSpanAssemblyRuntimeError(
                f"Unable to inspect span video with ffprobe: {candidate}: {exc}"
            ) from exc
        streams = raw.get("streams") if isinstance(raw, dict) else None
        if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
            raise GovernedSpanAssemblyRuntimeError(
                f"ffprobe did not return exactly one selected video stream: {candidate}"
            )
        stream = streams[0]
        frame_count = self._frame_count(stream)
        fps = self._fps(stream.get("r_frame_rate"))
        return SpanMediaObservation(
            path=candidate,
            frame_count=frame_count,
            width=self._positive_int(stream.get("width"), "width"),
            height=self._positive_int(stream.get("height"), "height"),
            frames_per_second=fps,
        )

    def _assemble(self, paths: tuple[Path, ...], destination: Path) -> None:
        with tempfile.TemporaryDirectory(prefix="vscs-span-assembly-") as temporary:
            list_path = Path(temporary) / "concat.txt"
            lines = []
            for path in paths:
                escaped = str(path).replace("'", "'\\''")
                lines.append(f"file '{escaped}'")
            list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            command = (
                self.ffmpeg,
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-map",
                "0:v:0",
                "-c",
                "copy",
                "-an",
                "-y",
                str(destination),
            )
            try:
                subprocess.run(command, check=True, capture_output=True, text=True)
            except (OSError, subprocess.CalledProcessError) as exc:
                raise GovernedSpanAssemblyRuntimeError(
                    "FFmpeg could not concatenate normalized span outputs without re-encoding"
                ) from exc

    @staticmethod
    def _frame_count(stream: dict[str, Any]) -> int:
        for key in ("nb_read_frames", "nb_frames"):
            raw = stream.get(key)
            if isinstance(raw, int) and raw > 0:
                return raw
            if isinstance(raw, str) and raw.isdigit() and int(raw) > 0:
                return int(raw)
        raise GovernedSpanAssemblyRuntimeError(
            "ffprobe did not expose an exact video frame count"
        )

    @staticmethod
    def _fps(raw: object) -> int:
        text = str(raw or "").strip()
        if not text:
            raise GovernedSpanAssemblyRuntimeError("ffprobe did not expose frame rate")
        try:
            value = Fraction(text)
        except (ValueError, ZeroDivisionError) as exc:
            raise GovernedSpanAssemblyRuntimeError(
                f"Invalid ffprobe frame rate: {text}"
            ) from exc
        if value.denominator != 1 or value.numerator <= 0:
            raise GovernedSpanAssemblyRuntimeError(
                f"Governed span assembly requires an integer frame rate, got {text}"
            )
        return value.numerator

    @staticmethod
    def _positive_int(raw: object, field_name: str) -> int:
        if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
            return raw
        if isinstance(raw, str) and raw.isdigit() and int(raw) > 0:
            return int(raw)
        raise GovernedSpanAssemblyRuntimeError(
            f"ffprobe returned invalid {field_name}: {raw!r}"
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
