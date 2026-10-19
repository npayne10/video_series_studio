"""Read-only governed assembly preview manifest and source-range verification.

A partial Draft can be previewed without claiming Episode completion or Picture Lock.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from vscs.application.assembly_contracts import AssemblyTimelineRevision
from vscs.application.episode_draft_selection import approval_evidence_reference
from vscs.application.episode_video_frame_inspection import read_approved_video_frames


@dataclass(frozen=True, slots=True)
class PreviewSegment:
    shot_id: str
    media_id: str
    relative_path: str
    source_in_frame: int
    source_out_frame: int
    source_frame_rate: Fraction
    timeline_start_frame: int
    timeline_end_frame: int


@dataclass(frozen=True, slots=True)
class AssemblyPreviewPlan:
    assembly_id: str
    revision_id: str
    revision_fingerprint: str
    segments: tuple[PreviewSegment, ...]
    blockers: tuple[str, ...]
    frame_rate: Fraction

    @property
    def ready(self) -> bool:
        return bool(self.segments) and not self.blockers

    @property
    def total_frames(self) -> int:
        return sum(
            segment.timeline_end_frame - segment.timeline_start_frame for segment in self.segments
        )


def inspect_assembly_preview(
    revision: AssemblyTimelineRevision,
    *,
    project_directory: Path,
    media_service: Any,
    validator: Any,
) -> AssemblyPreviewPlan:
    """Revalidate persisted source bytes and actual video frames, without rendering.

    Reject mismatched source frame rates rather than silently resampling.
    No writes, media approval or state transition are performed.
    """
    blockers: list[str] = []
    result = validator.validate(revision, final_use=True)
    blockers.extend(result.blockers)
    segments: list[PreviewSegment] = []
    position = 0
    target_rate = Fraction(revision.frame_rate_num, revision.frame_rate_den)
    if not revision.selections:
        blockers.append("Timeline contains no Shot selections")
    for selection in revision.selections:
        try:
            record = media_service.get(selection.generated_media_id)
            if record is None:
                raise ValueError("Source media record missing")
            if (
                record.scope.production_id != revision.scope.production_id
                or record.scope.episode_id != revision.scope.scope_id
                or record.scope.scene_id != selection.scene_id
                or record.scope.shot_id != selection.shot_id
                or str(record.revision) != selection.media_revision
                or record.file.checksum_sha256 != selection.file_checksum
                or selection.media_state != "approved"
                or approval_evidence_reference(record) != selection.approval_evidence_ref
            ):
                raise ValueError("Persisted source identity or approval evidence mismatches")
            details = read_approved_video_frames(project_directory, record)
            if selection.source_out_frame > details.frame_count:
                raise ValueError("Source frame range exceeds actual decoded frames")
            if details.frame_rate != target_rate:
                raise ValueError(
                    f"Source rate {details.frame_rate} differs from timeline rate {target_rate}"
                )
            segments.append(
                PreviewSegment(
                    shot_id=selection.shot_id,
                    media_id=selection.generated_media_id,
                    relative_path=details.relative_path,
                    source_in_frame=selection.source_in_frame,
                    source_out_frame=selection.source_out_frame,
                    source_frame_rate=details.frame_rate,
                    timeline_start_frame=position,
                    timeline_end_frame=position + selection.frame_count,
                )
            )
            position += selection.frame_count
        except (ValueError, OSError, RuntimeError) as exc:
            blockers.append(f"{selection.shot_id}: {exc}")
    return AssemblyPreviewPlan(
        assembly_id=revision.assembly_id,
        revision_id=revision.revision_id,
        revision_fingerprint=revision.fingerprint,
        segments=tuple(segments),
        blockers=tuple(blockers),
        frame_rate=target_rate,
    )
