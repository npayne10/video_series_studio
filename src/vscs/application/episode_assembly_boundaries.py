"""Verified, read-only decoded boundary frames for adjacent approved Shots."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vscs.application.episode_assembly_playback import validated_source_path
from vscs.application.episode_assembly_preview import AssemblyPreviewPlan, PreviewSegment


@dataclass(frozen=True)
class BoundaryPair:
    outgoing: PreviewSegment
    incoming: PreviewSegment
    outgoing_frame: int
    incoming_frame: int


def boundary_pair(plan: AssemblyPreviewPlan, index: int) -> BoundaryPair:
    if not plan.ready:
        raise ValueError("Verify all approved source media before boundary inspection")
    if index < 0 or index + 1 >= len(plan.segments):
        raise ValueError("Boundary index does not reference adjacent Shots")
    outgoing, incoming = plan.segments[index : index + 2]
    if outgoing.timeline_end_frame != incoming.timeline_start_frame:
        raise ValueError("Timeline boundary is not contiguous")
    return BoundaryPair(
        outgoing, incoming, outgoing.source_out_frame - 1, incoming.source_in_frame
    )


def extract_verified_boundary_png(
    project_directory: Path,
    segment: PreviewSegment,
    frame: int,
    *,
    ffmpeg_command: str = "ffmpeg",
    runner: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
) -> bytes:
    """Decode one exact numbered video frame into memory; never write source media."""
    if not segment.source_in_frame <= frame < segment.source_out_frame:
        raise ValueError("Requested frame lies outside approved source range")
    path = validated_source_path(project_directory, segment)
    try:
        result = runner(
            [
                ffmpeg_command,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-i",
                str(path),
                "-vf",
                f"select=eq(n\\,{frame})",
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ],
            capture_output=True,
            check=True,
            timeout=90,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Boundary frame decoding failed") from exc
    if not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Decoder returned no valid PNG frame")
    return result.stdout
