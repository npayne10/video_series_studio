"""Offline B.5.14 acceptance must never write project CAPs or call AI."""

from vscs.application.caps.spatial_acceptance import (
    AcceptanceScenario,
    run_spatial_acceptance,
)
from vscs.application.caps.spatial_report import SpatialReviewStatus


def test_valid_two_asset_room_is_verified_only_within_model():
    result = run_spatial_acceptance(AcceptanceScenario.VALID)
    assert result.report.status is SpatialReviewStatus.VERIFIED_WITHIN_MODEL
    assert result.report.placed_asset_ids == ("TEST-PRP-001", "TEST-PRP-002")
    assert result.report.rows == ()


def test_deliberate_sibling_overlap_is_reported_as_conflict():
    result = run_spatial_acceptance(AcceptanceScenario.COLLISION)
    assert result.report.status is SpatialReviewStatus.CONFLICT
    assert any(
        row.code == "collision" and set(row.asset_ids) == {"TEST-PRP-001", "TEST-PRP-002"}
        for row in result.report.rows
    )


def test_missing_second_geometry_is_unverified_not_approved():
    result = run_spatial_acceptance(AcceptanceScenario.MISSING_GEOMETRY)
    assert result.report.status is SpatialReviewStatus.UNVERIFIED
    assert result.report.placed_asset_ids == ("TEST-PRP-001",)
    assert any(row.code == "missing_child_geometry" for row in result.report.rows)


def test_repeated_runs_are_deterministic_and_isolated():
    for scenario in AcceptanceScenario:
        assert run_spatial_acceptance(scenario) == run_spatial_acceptance(scenario)
