"""B.5.13 operator statuses are conservative and do not imply Canon."""

from vscs.application.caps.spatial_graph import SpatialGraphFinding, SpatialGraphReport
from vscs.application.caps.spatial_report import (
    SpatialReviewStatus,
    build_spatial_review_report,
)


def test_missing_parent_geometry_is_unverified():
    graph = SpatialGraphReport(
        "CAP-LOC-001",
        (),
        (
            SpatialGraphFinding(
                "missing_parent_geometry", "Parent geometry missing", ("CAP-LOC-001",)
            ),
        ),
        False,
    )
    report = build_spatial_review_report(graph)
    assert report.status is SpatialReviewStatus.UNVERIFIED
    assert report.rows[0].asset_ids == ("CAP-LOC-001",)


def test_collision_is_conflict_with_pair_identity():
    graph = SpatialGraphReport(
        "CAP-LOC-001",
        ("CAP-PRP-001", "CAP-PRP-002"),
        (
            SpatialGraphFinding(
                "collision", "Sibling occupied volumes overlap", ("CAP-PRP-001", "CAP-PRP-002")
            ),
        ),
        False,
    )
    report = build_spatial_review_report(graph)
    assert report.status is SpatialReviewStatus.CONFLICT
    assert report.rows[0].status is SpatialReviewStatus.CONFLICT


def test_complete_placed_graph_is_only_verified_within_model():
    graph = SpatialGraphReport("CAP-LOC-001", ("CAP-PRP-001",), (), True)
    report = build_spatial_review_report(graph)
    assert report.status is SpatialReviewStatus.VERIFIED_WITHIN_MODEL
    assert "never approves" in report.scope_note


def test_empty_graph_is_never_reported_verified():
    report = build_spatial_review_report(SpatialGraphReport("CAP-LOC-001", (), (), True))
    assert report.status is SpatialReviewStatus.UNVERIFIED
