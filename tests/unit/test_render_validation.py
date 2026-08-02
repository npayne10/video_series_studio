"""Tests for Phase 15.5 render validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from vscs.application.acpp import (
    RenderCapability,
    RenderJob,
    RenderQualityMode,
    RetryPolicy,
    SeedPolicy,
)
from vscs.application.production_pipeline import ExecutionResult, ExecutorErrorCode
from vscs.infrastructure.production import (
    MediaProbeResult,
    RenderValidationPolicy,
    RenderValidationSeverity,
    RenderValidator,
)

NOW = datetime.now(UTC)


class StubProbe:
    def __init__(
        self,
        result: MediaProbeResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error

    def probe(self, path: Path) -> MediaProbeResult:
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return MediaProbeResult(
            path=path,
            width=1920,
            height=800,
            frames_per_second=24.0,
            frame_count=240,
            duration_seconds=10.0,
            container="mp4",
            video_codec="h264",
            has_video=True,
        )


def _job() -> RenderJob:
    return RenderJob(
        job_id="JOB-001",
        clip_id="CLIP-001",
        width=1920,
        height=800,
        frames_per_second=24,
        frame_count=240,
        quality_mode=RenderQualityMode.PRODUCTION,
        seed_policy=SeedPolicy.FIXED,
        fixed_seed=42,
        positive_prompt="James stands on the bridge.",
        negative_prompt="No drift.",
        input_references=(),
        start_reference_id=None,
        end_reference_id=None,
        output_path="production/clip-001.mp4",
        dependencies=(),
        retry_policy=RetryPolicy(),
        required_capabilities=(RenderCapability.TEXT_TO_VIDEO,),
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
    )


def _execution(path: Path, *, succeeded: bool = True) -> ExecutionResult:
    return ExecutionResult(
        job_id="JOB-001",
        worker_id="worker-a",
        succeeded=succeeded,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=10),
        output_paths=(str(path),) if succeeded else (),
        error_code=None if succeeded else ExecutorErrorCode.PROVIDER_ERROR,
        error_message=None if succeeded else "provider failed",
    )


def test_valid_render_passes_and_captures_checksum(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"render-data")

    result = RenderValidator(StubProbe()).validate(_job(), _execution(output))

    assert result.passed is True
    assert len(result.outputs) == 1
    assert result.outputs[0].checksum is not None
    assert result.outputs[0].size_bytes == len(b"render-data")


def test_missing_and_empty_outputs_fail(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    validator = RenderValidator(StubProbe())

    missing_result = validator.validate(_job(), _execution(missing))
    empty_result = validator.validate(_job(), _execution(empty))

    assert {item.code for item in missing_result.issues} == {"OUTPUT_MISSING"}
    assert {item.code for item in empty_result.issues} == {"OUTPUT_EMPTY"}


def test_failed_execution_and_job_mismatch_are_reported(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"render")
    execution = _execution(output, succeeded=False)
    execution = ExecutionResult(
        job_id="JOB-OTHER",
        worker_id=execution.worker_id,
        succeeded=False,
        started_at=execution.started_at,
        completed_at=execution.completed_at,
        error_code=execution.error_code,
        error_message=execution.error_message,
    )

    result = RenderValidator(StubProbe()).validate(_job(), execution)

    assert {item.code for item in result.issues} == {
        "EXECUTION_FAILED",
        "JOB_ID_MISMATCH",
        "NO_OUTPUTS",
    }


def test_probe_failure_is_reported(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"render")

    result = RenderValidator(StubProbe(error=ValueError("invalid media"))).validate(
        _job(),
        _execution(output),
    )

    assert result.passed is False
    assert result.issues[0].code == "PROBE_FAILED"


def test_technical_mismatches_fail_by_default(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"render")
    measured = MediaProbeResult(
        path=output,
        width=1280,
        height=720,
        frames_per_second=25.0,
        frame_count=250,
        duration_seconds=9.0,
        has_video=False,
    )

    result = RenderValidator(StubProbe(measured)).validate(_job(), _execution(output))

    assert result.passed is False
    assert {item.code for item in result.issues} == {
        "VIDEO_STREAM_MISSING",
        "WIDTH_MISMATCH",
        "HEIGHT_MISMATCH",
        "FRAME_RATE_MISMATCH",
        "FRAME_COUNT_MISMATCH",
        "DURATION_MISMATCH",
    }


def test_metadata_mismatches_can_be_warnings(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"render")
    measured = MediaProbeResult(
        path=output,
        width=1280,
        height=720,
        frames_per_second=25.0,
        frame_count=250,
        duration_seconds=9.0,
        has_video=True,
    )
    policy = RenderValidationPolicy(metadata_mismatches_are_warnings=True)

    result = RenderValidator(StubProbe(measured), policy).validate(
        _job(),
        _execution(output),
    )

    assert result.passed is True
    assert result.warnings
    assert all(
        item.severity is RenderValidationSeverity.WARNING for item in result.warnings
    )


def test_tolerances_and_checksum_policy_are_applied(tmp_path: Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"render")
    measured = MediaProbeResult(
        path=output,
        width=1920,
        height=800,
        frames_per_second=24.04,
        frame_count=241,
        duration_seconds=10.08,
        has_video=True,
    )
    policy = RenderValidationPolicy(
        frame_rate_tolerance=0.05,
        frame_count_tolerance=1,
        duration_tolerance_seconds=0.1,
        checksum_outputs=False,
    )

    result = RenderValidator(StubProbe(measured), policy).validate(
        _job(),
        _execution(output),
    )

    assert result.passed is True
    assert result.outputs[0].checksum is None
