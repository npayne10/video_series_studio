"""Read actual approved project video metadata for Draft source-range assistance."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VerifiedVideoFrames:
    media_id: str
    relative_path: str
    frame_count: int
    frame_rate: Fraction

    @property
    def duration_seconds(self) -> float:
        return float(self.frame_count / self.frame_rate)


def read_approved_video_frames(
    project_directory: Path,
    record: Any,
    *,
    probe_command: str = "ffprobe",
) -> VerifiedVideoFrames:
    """Verify persisted media and count frames via ffprobe; never grant approval."""
    if (
        getattr(record.kind, "value", "") != "video"
        or record.state.value != "approved"
        or not any(event.to_state.value == "approved" for event in record.governance_history)
    ):
        raise ValueError("Only human-approved video media may be inspected")
    root = Path(project_directory).resolve()
    relative_path = record.file.relative_path
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Approved media file missing or outside project")
    if not record.file.checksum_sha256 or record.file.size_bytes is None:
        raise ValueError("Media integrity evidence unavailable")
    digest = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            count += len(chunk)
    if count != record.file.size_bytes or digest.hexdigest() != record.file.checksum_sha256:
        raise ValueError("Approved media file checksum or size mismatch")
    try:
        process = subprocess.run(
            [
                probe_command, "-v", "error", "-select_streams", "v:0",
                "-count_frames", "-show_entries",
                "stream=nb_read_frames,avg_frame_rate", "-of", "json", str(path),
            ],
            check=True, capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(process.stdout)
        streams = payload["streams"]
        if len(streams) != 1:
            raise ValueError("Expected exactly one video stream")
        frames = int(streams[0]["nb_read_frames"])
        rate = Fraction(streams[0]["avg_frame_rate"])
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Video metadata inspection unavailable or failed") from exc
    except (KeyError, TypeError, ValueError, ZeroDivisionError, json.JSONDecodeError) as exc:
        raise ValueError("Video frame count or frame rate is invalid") from exc
    if frames <= 0 or rate <= 0:
        raise ValueError("Video must have a positive frame count and frame rate")
    return VerifiedVideoFrames(record.media_id, relative_path, frames, rate)
