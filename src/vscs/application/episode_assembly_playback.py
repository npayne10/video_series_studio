"""Read-only frame-to-media routing for governed sequential Qt playback."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from vscs.application.episode_assembly_preview import AssemblyPreviewPlan, PreviewSegment


@dataclass(frozen=True, slots=True)
class PlaybackPosition:
    segment_index: int
    segment: PreviewSegment
    source_ms: int


def map_timeline_frame(plan: AssemblyPreviewPlan, frame: int) -> PlaybackPosition:
    """Map an in-range assembly frame to its actual source presentation time."""
    if not plan.ready:
        raise ValueError("Playback requires a fully verified preview")
    if frame < 0 or frame >= plan.total_frames:
        raise ValueError("Timeline frame outside verified preview")
    for index, segment in enumerate(plan.segments):
        if segment.timeline_start_frame <= frame < segment.timeline_end_frame:
            source_frame = segment.source_in_frame + frame - segment.timeline_start_frame
            position = Fraction(source_frame * 1000, 1) / segment.source_frame_rate
            return PlaybackPosition(index, segment, int(position))
    raise ValueError("Timeline contains an unassigned frame")


def validated_source_path(project_directory: Path, segment: PreviewSegment) -> Path:
    """Resolve only local files inside the verified project directory."""
    root = Path(project_directory).resolve()
    path = (root / segment.relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Preview source file is missing or outside the project")
    return path
