"""Tests for deterministic SSIE scene and shot planning."""
from __future__ import annotations

import pytest

from vscs.application.ssie import (
    RuleBasedScenePlanner,
    RuleBasedShotPlanner,
    Scene,
    ScenePlanningError,
    SceneTransition,
    ShotPurpose,
)


def _scene(**overrides: object) -> Scene:
    values: dict[str, object] = {
        "scene_id": "SCN-001",
        "episode_id": "EP-001",
        "sequence_number": 1,
        "heading": "INT. OBSERVATION LOUNGE - NIGHT",
        "location_asset_id": "LOC-OBS-001",
        "summary": "James discovers an unexplained signal beyond the ship.",
        "participant_asset_ids": ("CHR-JAMES-001", "CHR-SANDRA-001"),
        "dialogue": ("That signal should not be there.", "I see it too."),
        "required_asset_ids": ("PROP-CONSOLE-001", "LOC-OBS-001"),
        "time_of_day": "night",
        "transition_in": SceneTransition.DISSOLVE,
        "estimated_duration_seconds": 40.0,
    }
    values.update(overrides)
    return Scene(**values)  # type: ignore[arg-type]


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
        ShotPurpose.MASTER,
        ShotPurpose.COVERAGE,
        ShotPurpose.COVERAGE,
        ShotPurpose.CLOSING,
    ]
    assert [shot.sequence_number for shot in plan.shots] == [1, 2, 3, 4, 5]
    assert all(shot.estimated_duration_seconds == 8.0 for shot in plan.shots)


def test_shot_planner_uses_action_coverage_without_dialogue() -> None:
    shots = RuleBasedShotPlanner().plan_shots(
        _scene(dialogue=(), participant_asset_ids=("CHR-JAMES-001",))
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
