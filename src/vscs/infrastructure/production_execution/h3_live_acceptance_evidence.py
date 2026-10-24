"""Q3.1.3.5.8b: offline H3 output integrity and write-once acceptance evidence.

No provider requests, generation or ProductionTask/QC mutations are performed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .h3_live_acceptance import H3IsolatedAcceptanceError


@dataclass(frozen=True, slots=True)
class H3ValidatedOutput:
    relative_path: str
    byte_count: int
    sha256: str
    frame_count: int
    frames_per_second: int
    width: int
    height: int


def validate_h3_acceptance_output(
    path: Path,
    *,
    allowed_root: Path,
    expected_frames: int,
    expected_fps: int,
    ffprobe: str = "ffprobe",
) -> H3ValidatedOutput:
    """Validate confined, nonempty MP4 using actual stream metadata."""
    root = Path(allowed_root).expanduser().resolve(strict=True)
    candidate = Path(path).expanduser().resolve(strict=True)
    if not root.is_dir() or candidate == root or not candidate.is_relative_to(root):
        raise H3IsolatedAcceptanceError("H3 output escapes authorized acceptance root")
    if not candidate.is_file() or candidate.suffix.lower() != ".mp4":
        raise H3IsolatedAcceptanceError("H3 output must be an MP4 file")
    byte_count = candidate.stat().st_size
    if byte_count <= 0:
        raise H3IsolatedAcceptanceError("H3 output is empty")
    if expected_frames <= 0 or expected_fps <= 0:
        raise H3IsolatedAcceptanceError("H3 output requires positive governed frames and FPS")
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-count_frames",
                "-show_entries",
                "stream=codec_type,width,height,nb_read_frames,avg_frame_rate",
                "-of",
                "json",
                str(candidate),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        metadata = json.loads(completed.stdout)
        stream = metadata["streams"][0]
        frames = int(stream["nb_read_frames"])
        rate = str(stream["avg_frame_rate"]).split("/")
        numerator = int(rate[0])
        denominator = int(rate[1]) if len(rate) == 2 else 1
        fps = numerator // denominator if denominator and numerator % denominator == 0 else 0
        width, height = int(stream["width"]), int(stream["height"])
    except (
        OSError,
        subprocess.SubprocessError,
        KeyError,
        ValueError,
        IndexError,
        TypeError,
        ZeroDivisionError,
    ) as exc:
        raise H3IsolatedAcceptanceError(f"H3 output media validation failed: {exc}") from exc
    if frames != expected_frames or fps != expected_fps or width <= 0 or height <= 0:
        raise H3IsolatedAcceptanceError("H3 output frame count, FPS or resolution is invalid")
    with candidate.open("rb") as handle:
        checksum = hashlib.file_digest(handle, "sha256").hexdigest()
    return H3ValidatedOutput(
        relative_path=candidate.relative_to(root).as_posix(),
        byte_count=byte_count,
        sha256=checksum,
        frame_count=frames,
        frames_per_second=fps,
        width=width,
        height=height,
    )


def write_h3_acceptance_evidence(
    *,
    evidence_root: Path,
    acceptance_project: Path,
    run_id: str,
    task_id: str,
    shot_id: str,
    plan_fingerprint: str,
    output: H3ValidatedOutput,
    provider_evidence: dict[str, object] | None = None,
) -> Path:
    """Create a write-once, unreviewed report without replacing existing evidence."""
    project = Path(acceptance_project).resolve(strict=True)
    root = Path(evidence_root).resolve(strict=True)
    if not root.is_dir() or root == project or not root.is_relative_to(project):
        raise H3IsolatedAcceptanceError("H3 evidence must reside inside disposable project")
    if not run_id or not run_id.replace("-", "").replace("_", "").isalnum():
        raise H3IsolatedAcceptanceError("H3 evidence requires a safe run identifier")
    if not task_id.strip() or not shot_id.strip() or not plan_fingerprint.strip():
        raise H3IsolatedAcceptanceError("H3 evidence is missing governed identity")
    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "task_id": task_id,
        "shot_id": shot_id,
        "plan_fingerprint": plan_fingerprint,
        "output": {
            "relative_path": output.relative_path,
            "byte_count": output.byte_count,
            "sha256": output.sha256,
            "frame_count": output.frame_count,
            "frames_per_second": output.frames_per_second,
            "width": output.width,
            "height": output.height,
        },
        "validation": "passed",
        "qc_status": "unreviewed",
        "approved": False,
    }
    if provider_evidence is not None:
        payload["provider_provenance"] = {
            key: provider_evidence.get(key)
            for key in (
                "provider_id",
                "job_id",
                "span_id",
                "prompt_id",
                "workflow_fingerprint",
                "model_config_fingerprint",
                "output_sha256",
            )
        }
    destination = root / f"{run_id}.json"
    try:
        with destination.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        raise H3IsolatedAcceptanceError("H3 acceptance evidence already exists") from exc
    return destination
