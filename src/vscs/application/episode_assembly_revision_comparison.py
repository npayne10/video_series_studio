"""Pure, immutable A/B comparison of persisted assembly timeline revisions."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from vscs.application.assembly_contracts import AssemblyTimelineRevision, ShotSelection


@dataclass(frozen=True, slots=True)
class RevisionDifference:
    shot_id: str
    change: str
    index_a: int | None
    index_b: int | None
    media_a: str | None
    media_b: str | None
    range_a: tuple[int, int] | None
    range_b: tuple[int, int] | None


@dataclass(frozen=True, slots=True)
class RevisionComparison:
    revision_a: str
    revision_b: str
    fingerprint_a: str
    fingerprint_b: str
    frames_a: int
    frames_b: int
    duration_a: Fraction
    duration_b: Fraction
    differences: tuple[RevisionDifference, ...]

    @property
    def frame_delta(self) -> int:
        return self.frames_b - self.frames_a

    @property
    def duration_delta(self) -> Fraction:
        return self.duration_b - self.duration_a


def _frame_range(item: ShotSelection | None) -> tuple[int, int] | None:
    return None if item is None else (item.source_in_frame, item.source_out_frame)


def compare_assembly_revisions(
    a: AssemblyTimelineRevision, b: AssemblyTimelineRevision
) -> RevisionComparison:
    """Compare same-assembly, same-scope revisions; never alter either."""
    if a.assembly_id != b.assembly_id or a.scope != b.scope:
        raise ValueError("A/B comparison requires identical assembly and authoritative scope")
    if (a.frame_rate_num, a.frame_rate_den) != (b.frame_rate_num, b.frame_rate_den):
        raise ValueError("A/B comparison requires matching timeline frame rates")
    if a.fingerprint == b.fingerprint:
        raise ValueError("Choose two distinct persisted revisions")
    by_a = {s.shot_id: s for s in a.selections}
    by_b = {s.shot_id: s for s in b.selections}
    diffs: list[RevisionDifference] = []
    ordered = list(dict.fromkeys([s.shot_id for s in a.selections + b.selections]))
    for shot_id in ordered:
        left, right = by_a.get(shot_id), by_b.get(shot_id)
        if left is None:
            change = "ADDED"
        elif right is None:
            change = "REMOVED"
        elif left == right:
            change = "UNCHANGED"
        else:
            flags = []
            if left.sequence_index != right.sequence_index:
                flags.append("ORDER")
            if (left.source_in_frame, left.source_out_frame) != (
                right.source_in_frame, right.source_out_frame
            ):
                flags.append("RANGE")
            if (
                left.generated_media_id != right.generated_media_id
                or left.media_revision != right.media_revision
                or left.file_checksum != right.file_checksum
                or left.approval_evidence_ref != right.approval_evidence_ref
                or left.media_state != right.media_state
                or left.boundary_evidence_refs != right.boundary_evidence_refs
            ):
                flags.append("MEDIA/EVIDENCE")
            change = " + ".join(flags) if flags else "MODIFIED"
        diffs.append(
            RevisionDifference(
                shot_id,
                change,
                None if left is None else left.sequence_index,
                None if right is None else right.sequence_index,
                None if left is None else left.generated_media_id,
                None if right is None else right.generated_media_id,
                _frame_range(left),
                _frame_range(right),
            )
        )
    return RevisionComparison(
        a.revision_id,
        b.revision_id,
        a.fingerprint,
        b.fingerprint,
        a.total_frames,
        b.total_frames,
        a.duration_seconds,
        b.duration_seconds,
        tuple(diffs),
    )
