"""Policy-driven validation for rendered production media."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from vscs.application.acpp import RenderJob
from vscs.application.production_pipeline import ExecutionResult


class RenderValidationSeverity(StrEnum):
    """Severity assigned to one render-validation finding."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class MediaProbeResult:
    """Measured media properties returned by a probe implementation."""

    path: Path
    width: int | None = None
    height: int | None = None
    frames_per_second: float | None = None
    frame_count: int | None = None
    duration_seconds: float | None = None
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    has_video: bool = True
    has_audio: bool = False
    metadata: tuple[tuple[str, str], ...] = ()


class MediaProbe(Protocol):
    """Inspect one media file and return measured technical properties."""

    def probe(self, path: Path) -> MediaProbeResult:
        """Probe one local media file."""
        ...


@dataclass(frozen=True, slots=True)
class RenderValidationPolicy:
    """Tolerance and severity policy for render validation."""

    frame_rate_tolerance: float = 0.01
    duration_tolerance_seconds: float = 0.1
    frame_count_tolerance: int = 0
    require_video_stream: bool = True
    require_nonempty_file: bool = True
    checksum_outputs: bool = True
    metadata_mismatches_are_warnings: bool = False

    def __post_init__(self) -> None:
        if self.frame_rate_tolerance < 0:
            raise ValueError("frame_rate_tolerance must not be negative")
        if self.duration_tolerance_seconds < 0:
            raise ValueError("duration_tolerance_seconds must not be negative")
        if self.frame_count_tolerance < 0:
            raise ValueError("frame_count_tolerance must not be negative")


@dataclass(frozen=True, slots=True)
class RenderValidationIssue:
    """One technical validation finding for a render output."""

    severity: RenderValidationSeverity
    code: str
    message: str
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class ValidatedRenderOutput:
    """Verified output metadata suitable for provenance capture."""

    path: Path
    checksum: str | None
    size_bytes: int
    probe: MediaProbeResult


@dataclass(frozen=True, slots=True)
class RenderValidationResult:
    """Complete validation outcome for one render job execution."""

    job_id: str
    clip_id: str
    outputs: tuple[ValidatedRenderOutput, ...]
    issues: tuple[RenderValidationIssue, ...]

    @property
    def passed(self) -> bool:
        """Return whether no error-severity findings were produced."""
        return not any(issue.severity is RenderValidationSeverity.ERROR for issue in self.issues)

    @property
    def warnings(self) -> tuple[RenderValidationIssue, ...]:
        """Return warning-severity findings."""
        return tuple(
            issue for issue in self.issues if issue.severity is RenderValidationSeverity.WARNING
        )


class RenderValidationError(RuntimeError):
    """Raised when render validation cannot be performed."""


class RenderValidator:
    """Validate executor outputs against one renderer-neutral render job."""

    def __init__(
        self,
        probe: MediaProbe,
        policy: RenderValidationPolicy | None = None,
    ) -> None:
        self.probe = probe
        self.policy = policy or RenderValidationPolicy()

    def validate(
        self,
        job: RenderJob,
        execution: ExecutionResult,
    ) -> RenderValidationResult:
        """Validate all outputs reported by one successful execution."""
        issues: list[RenderValidationIssue] = []
        outputs: list[ValidatedRenderOutput] = []
        if execution.job_id != job.job_id:
            issues.append(
                self._issue(
                    "JOB_ID_MISMATCH",
                    "Execution result job ID does not match render job",
                )
            )
        if not execution.succeeded:
            issues.append(
                self._issue(
                    "EXECUTION_FAILED",
                    execution.error_message or "Render execution did not succeed",
                )
            )
        if not execution.output_paths:
            issues.append(self._issue("NO_OUTPUTS", "Execution reported no output paths"))

        for value in execution.output_paths:
            path = Path(value)
            if not path.is_file():
                issues.append(
                    self._issue("OUTPUT_MISSING", f"Render output not found: {path}", path)
                )
                continue
            size_bytes = path.stat().st_size
            if self.policy.require_nonempty_file and size_bytes <= 0:
                issues.append(self._issue("OUTPUT_EMPTY", f"Render output is empty: {path}", path))
                continue
            try:
                measured = self.probe.probe(path)
            except (OSError, ValueError, RuntimeError) as exc:
                issues.append(self._issue("PROBE_FAILED", f"Unable to probe {path}: {exc}", path))
                continue
            self._validate_probe(job, measured, issues)
            checksum = self.file_checksum(path) if self.policy.checksum_outputs else None
            outputs.append(ValidatedRenderOutput(path, checksum, size_bytes, measured))

        return RenderValidationResult(
            job_id=job.job_id,
            clip_id=job.clip_id,
            outputs=tuple(outputs),
            issues=tuple(issues),
        )

    def _validate_probe(
        self,
        job: RenderJob,
        measured: MediaProbeResult,
        issues: list[RenderValidationIssue],
    ) -> None:
        path = measured.path
        if self.policy.require_video_stream and not measured.has_video:
            issues.append(self._issue("VIDEO_STREAM_MISSING", "No video stream found", path))
        self._compare_int("WIDTH_MISMATCH", job.width, measured.width, path, issues)
        self._compare_int("HEIGHT_MISMATCH", job.height, measured.height, path, issues)
        if (
            measured.frames_per_second is not None
            and abs(measured.frames_per_second - job.frames_per_second)
            > self.policy.frame_rate_tolerance
        ):
            issues.append(
                self._metadata_issue(
                    "FRAME_RATE_MISMATCH",
                    f"Expected {job.frames_per_second} fps, found "
                    f"{measured.frames_per_second:g} fps",
                    path,
                )
            )
        if (
            measured.frame_count is not None
            and abs(measured.frame_count - job.frame_count) > self.policy.frame_count_tolerance
        ):
            issues.append(
                self._metadata_issue(
                    "FRAME_COUNT_MISMATCH",
                    f"Expected {job.frame_count} frames, found {measured.frame_count}",
                    path,
                )
            )
        expected_duration = job.frame_count / job.frames_per_second
        if (
            measured.duration_seconds is not None
            and abs(measured.duration_seconds - expected_duration)
            > self.policy.duration_tolerance_seconds
        ):
            issues.append(
                self._metadata_issue(
                    "DURATION_MISMATCH",
                    f"Expected {expected_duration:.3f}s, found {measured.duration_seconds:.3f}s",
                    path,
                )
            )

    def _compare_int(
        self,
        code: str,
        expected: int,
        actual: int | None,
        path: Path,
        issues: list[RenderValidationIssue],
    ) -> None:
        if actual is not None and actual != expected:
            issues.append(
                self._metadata_issue(
                    code,
                    f"Expected {expected}, found {actual}",
                    path,
                )
            )

    def _metadata_issue(
        self,
        code: str,
        message: str,
        path: Path,
    ) -> RenderValidationIssue:
        severity = (
            RenderValidationSeverity.WARNING
            if self.policy.metadata_mismatches_are_warnings
            else RenderValidationSeverity.ERROR
        )
        return RenderValidationIssue(severity, code, message, path)

    @staticmethod
    def _issue(
        code: str,
        message: str,
        path: Path | None = None,
    ) -> RenderValidationIssue:
        return RenderValidationIssue(RenderValidationSeverity.ERROR, code, message, path)

    @staticmethod
    def file_checksum(path: Path) -> str:
        """Return the SHA-256 checksum for one output file."""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
