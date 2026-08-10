"""Tests for deterministic SSIE scene and shot planning."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.ssie import (
    PacingProfile,
    RuleBasedScenePlanner,
    RuleBasedShotPlanner,
    Scene,
    ScenePlanningError,
    ScenePurpose,
    SceneTransition,
    ShotPlannerConfig,
    ShotPurpose,
)


def _scene(**overrides: object) -> Scene:
    scene = Scene(
        scene_id="SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. OBSERVATION LOUNGE - NIGHT",
        location_asset_id="LOC-OBS-001",
        summary="James discovers an unexplained signal beyond the ship.",
        participant_asset_ids=("CHR-JAMES-001", "CHR-SANDRA-001"),
        dialogue=("That signal should not be there.", "I see it too."),
        required_asset_ids=("PROP-CONSOLE-001", "LOC-OBS-001"),
        time_of_day="night",
        transition_in=SceneTransition.DISSOLVE,
        estimated_duration_seconds=40.0,
    )
    return replace(scene, **overrides)


def test_scene_planner_builds_valid_dialogue_plan() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())

    assert plan.objective.startswith("Dramatise the scene outcome:")
    assert plan.emotional_intent == "Controlled wonder"
    assert plan.required_asset_ids == (
        "LOC-OBS-001",
        "CHR-JAMES-001",
        "CHR-SANDRA-001",
        "PROP-CONSOLE-001",
    )
    assert [shot.purpose for shot in plan.shots] == [
        ShotPurpose.ESTABLISHING,
        ShotPurpose.TRANSITION,
        ShotPurpose.MASTER,
        ShotPurpose.COVERAGE,
        ShotPurpose.COVERAGE,
        ShotPurpose.INSERT,
        ShotPurpose.CLOSING,
    ]
    assert [shot.sequence_number for shot in plan.shots] == list(range(1, 8))
    assert all(shot.estimated_duration_seconds == 5.714 for shot in plan.shots)


def test_shot_planner_uses_action_coverage_without_dialogue() -> None:
    shots = RuleBasedShotPlanner().plan_shots(
        _scene(
            dialogue=(),
            participant_asset_ids=("CHR-JAMES-001",),
            summary="James crosses the observation lounge.",
            transition_in=SceneTransition.CUT,
            required_asset_ids=(),
        )
    )

    assert [shot.purpose for shot in shots] == [
        ShotPurpose.ESTABLISHING,
        ShotPurpose.ACTION,
        ShotPurpose.CLOSING,
    ]
    assert shots[1].subject_asset_ids == ("CHR-JAMES-001",)


def test_scene_planner_maps_tension_keywords() -> None:
    plan = RuleBasedScenePlanner().plan_scene(
        _scene(summary="An alarm warns of an imminent attack.")
    )

    assert plan.emotional_intent == "Sustained tension"


def test_scene_planner_rejects_invalid_scene() -> None:
    with pytest.raises(ScenePlanningError) as error:
        RuleBasedScenePlanner().plan_scene(_scene(scene_id="", sequence_number=0))

    codes = {issue.code for issue in error.value.issues}
    assert "REQUIRED_TEXT_MISSING" in codes
    assert "INVALID_SCENE_SEQUENCE" in codes


def test_shot_planner_classifies_conflict_and_adds_reaction() -> None:
    planner = RuleBasedShotPlanner()
    scene = _scene(
        summary="James confronts Sandra over the concealed order.",
        transition_in=SceneTransition.CUT,
        required_asset_ids=(),
    )

    analysis = planner.analyse_scene(scene)
    shots = planner.plan_shots(scene)

    assert analysis.scene_purpose is ScenePurpose.CONFLICT
    assert analysis.pacing is PacingProfile.URGENT
    assert ShotPurpose.REACTION in {shot.purpose for shot in shots}


def test_shot_planner_segments_urgent_action() -> None:
    planner = RuleBasedShotPlanner()
    shots = planner.plan_shots(
        _scene(
            summary="James races to escape an imminent attack.",
            dialogue=(),
            transition_in=SceneTransition.CUT,
            required_asset_ids=(),
        )
    )

    assert [shot.purpose for shot in shots].count(ShotPurpose.ACTION) == 2
    assert all(shot.estimated_duration_seconds == 8.5 for shot in shots)


def test_shot_planner_respects_shot_limit() -> None:
    planner = RuleBasedShotPlanner(ShotPlannerConfig(maximum_shots=4))
    shots = planner.plan_shots(
        _scene(
            participant_asset_ids=(
                "CHR-JAMES-001",
                "CHR-SANDRA-001",
                "CHR-CHERYL-001",
                "CHR-ROS-001",
            ),
            transition_in=SceneTransition.CUT,
            summary="The officers review the mission plan.",
            required_asset_ids=(),
        )
    )

    assert len(shots) == 4
    assert shots[0].purpose is ShotPurpose.ESTABLISHING
    assert shots[-1].purpose is ShotPurpose.CLOSING
    assert [shot.sequence_number for shot in shots] == [1, 2, 3, 4]


def test_shot_planner_validates_configuration() -> None:
    with pytest.raises(ValueError, match="maximum_shots"):
        ShotPlannerConfig(maximum_shots=1)

    with pytest.raises(ValueError, match="maximum shot duration"):
        ShotPlannerConfig(
            minimum_shot_duration_seconds=5.0,
            maximum_shot_duration_seconds=4.0,
        )
