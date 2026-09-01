from __future__ import annotations

from vscs.infrastructure.production_execution.provider_segmentation import (
    GovernedProviderSegmentationPlanner,
    ProviderSegmentationPolicy,
)


def test_528_frames_balance_into_three_governed_execution_segments() -> None:
    planner = GovernedProviderSegmentationPlanner()

    plan = planner.plan(frame_count=528, frames_per_second=24, seed=1000)

    assert plan["mode"] == "segmented"
    assert plan["segment_count"] == 3
    assert plan["governed_frame_count"] == 528
    assert plan["governed_duration_seconds"] == 22.0
    segments = plan["segments"]
    assert [segment["frame_count"] for segment in segments] == [176, 176, 176]
    assert [segment["start_frame"] for segment in segments] == [0, 176, 352]
    assert [segment["end_frame"] for segment in segments] == [175, 351, 527]
    assert [segment["seed"] for segment in segments] == [1000, 1001, 1002]
    assert segments[0]["continuity_input"] == "governed_initial_reference"
    assert segments[1]["continuity_input"] == "previous_segment_final_frame"
    assert plan["assembly"]["required"] is True


def test_frame_count_at_limit_remains_monolithic() -> None:
    planner = GovernedProviderSegmentationPlanner()

    plan = planner.plan(frame_count=192, frames_per_second=24, seed=42)

    assert plan["mode"] == "monolithic"
    assert plan["segment_count"] == 1
    assert plan["segments"][0]["frame_count"] == 192
    assert plan["assembly"]["required"] is False


def test_custom_policy_balances_without_losing_frames() -> None:
    planner = GovernedProviderSegmentationPlanner(
        ProviderSegmentationPolicy(max_frames_per_segment=100)
    )

    plan = planner.plan(frame_count=250, frames_per_second=25, seed=7)

    assert plan["segment_count"] == 3
    assert [segment["frame_count"] for segment in plan["segments"]] == [84, 83, 83]
    assert sum(segment["frame_count"] for segment in plan["segments"]) == 250
    assert plan["segments"][-1]["end_frame"] == 249


def test_invalid_dimensions_are_rejected() -> None:
    planner = GovernedProviderSegmentationPlanner()

    try:
        planner.plan(frame_count=0, frames_per_second=24, seed=1)
    except ValueError as exc:
        assert "frame_count" in str(exc)
    else:
        raise AssertionError("Expected invalid frame_count to be rejected")

    try:
        planner.plan(frame_count=24, frames_per_second=0, seed=1)
    except ValueError as exc:
        assert "frames_per_second" in str(exc)
    else:
        raise AssertionError("Expected invalid frames_per_second to be rejected")
