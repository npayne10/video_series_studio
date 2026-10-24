"""Q3.1.3.5.8b: isolated output validation and write-once QC-safe evidence."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from vscs.infrastructure.production_execution.h3_live_acceptance import (
    H3IsolatedAcceptanceError,
)
from vscs.infrastructure.production_execution.h3_live_acceptance_evidence import (
    validate_h3_acceptance_output,
    write_h3_acceptance_evidence,
)


def _valid_video(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    target = root / "accepted.mp4"
    subprocess.run(
        [
            "ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi",
            "-i", "color=c=black:s=64x64:r=24", "-frames:v", "12",
            "-c:v", "mpeg4", str(target),
        ],
        check=True, capture_output=True, timeout=30,
    )
    return target


def test_real_ffprobe_accepts_expected_mp4_and_writes_unreviewed_evidence(tmp_path: Path):
    project = tmp_path / "disposable-project"
    output_root = project / "output"
    evidence_root = project / "evidence"
    evidence_root.mkdir(parents=True)
    target = _valid_video(output_root)
    result = validate_h3_acceptance_output(
        target, allowed_root=output_root, expected_frames=12, expected_fps=24
    )
    assert result.frame_count == 12
    assert result.frames_per_second == 24
    assert result.byte_count > 0
    assert len(result.sha256) == 64
    path = write_h3_acceptance_evidence(
        evidence_root=evidence_root, acceptance_project=project, run_id="RUN-001",
        task_id="TEST-TASK", shot_id="TEST-SHOT", plan_fingerprint="plan-test",
        output=result,
    )
    report = json.loads(path.read_text(encoding="utf-8"))
    assert report["qc_status"] == "unreviewed"
    assert report["approved"] is False
    assert report["output"]["sha256"] == result.sha256
    with pytest.raises(H3IsolatedAcceptanceError, match="already exists"):
        write_h3_acceptance_evidence(
            evidence_root=evidence_root, acceptance_project=project, run_id="RUN-001",
            task_id="TEST-TASK", shot_id="TEST-SHOT", plan_fingerprint="plan-test",
            output=result,
        )


def test_wrong_frame_count_blocks(tmp_path: Path):
    target = _valid_video(tmp_path / "output")
    with pytest.raises(H3IsolatedAcceptanceError, match="frame count"):
        validate_h3_acceptance_output(
            target, allowed_root=target.parent, expected_frames=13, expected_fps=24
        )


def test_corrupt_mp4_blocks(tmp_path: Path):
    root = tmp_path / "output"
    root.mkdir()
    bad = root / "corrupt.mp4"
    bad.write_bytes(b"not really mp4")
    with pytest.raises(H3IsolatedAcceptanceError, match="validation failed"):
        validate_h3_acceptance_output(
            bad, allowed_root=root, expected_frames=12, expected_fps=24
        )


def test_empty_mp4_blocks(tmp_path: Path):
    root = tmp_path / "output"
    root.mkdir()
    bad = root / "empty.mp4"
    bad.touch()
    with pytest.raises(H3IsolatedAcceptanceError, match="empty"):
        validate_h3_acceptance_output(
            bad, allowed_root=root, expected_frames=12, expected_fps=24
        )


def test_output_outside_root_blocks(tmp_path: Path):
    root = tmp_path / "output"
    root.mkdir()
    external = tmp_path / "outside.mp4"
    external.write_bytes(b"data")
    with pytest.raises(H3IsolatedAcceptanceError, match="escapes"):
        validate_h3_acceptance_output(
            external, allowed_root=root, expected_frames=12, expected_fps=24
        )


def test_evidence_outside_project_blocks(tmp_path: Path):
    project = tmp_path / "project"
    project.mkdir()
    external = tmp_path / "evidence"
    external.mkdir()
    from vscs.infrastructure.production_execution.h3_live_acceptance_evidence import (
        H3ValidatedOutput,
    )

    result = H3ValidatedOutput("x.mp4", 10, "a" * 64, 12, 24, 64, 64)
    with pytest.raises(H3IsolatedAcceptanceError, match="inside disposable"):
        write_h3_acceptance_evidence(
            evidence_root=external, acceptance_project=project, run_id="RUN-001",
            task_id="TASK", shot_id="SHOT", plan_fingerprint="plan", output=result,
        )
