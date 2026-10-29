"""Operator-facing, read-only spatial continuity report classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.caps.spatial_graph import SpatialGraphReport

_CONFLICT_CODES = frozenset({"collision", "out_of_bounds", "frame_mismatch", "missing_anchor"})


class SpatialReviewStatus(StrEnum):
    VERIFIED_WITHIN_MODEL = "verified_within_model"
    UNVERIFIED = "unverified"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class SpatialReviewRow:
    asset_ids: tuple[str, ...]
    status: SpatialReviewStatus
    code: str
    detail: str


@dataclass(frozen=True)
class SpatialReviewReport:
    parent_asset_id: str
    status: SpatialReviewStatus
    placed_asset_ids: tuple[str, ...]
    rows: tuple[SpatialReviewRow, ...]
    scope_note: str = (
        "Local, axis-aligned geometry only. This report never approves Story Canon, "
        "CAPs, references, or generation."
    )


def build_spatial_review_report(graph: SpatialGraphReport) -> SpatialReviewReport:
    """Conservatively classify all findings; missing coverage is not a pass."""
    rows = tuple(
        SpatialReviewRow(
            item.asset_ids,
            (
                SpatialReviewStatus.CONFLICT
                if item.code in _CONFLICT_CODES
                else SpatialReviewStatus.UNVERIFIED
            ),
            item.code,
            item.message,
        )
        for item in graph.findings
    )
    if any(row.status is SpatialReviewStatus.CONFLICT for row in rows):
        status = SpatialReviewStatus.CONFLICT
    elif rows or not graph.verified or not graph.placed_asset_ids:
        status = SpatialReviewStatus.UNVERIFIED
    else:
        status = SpatialReviewStatus.VERIFIED_WITHIN_MODEL
    return SpatialReviewReport(graph.parent_asset_id, status, graph.placed_asset_ids, rows)
