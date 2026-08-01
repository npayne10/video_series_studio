"""Tests for SSIE camera, lighting, blocking, and continuity planning."""
from __future__ import annotations

from dataclasses import replace

from vscs.application.ssie import (
    BlockingPattern,
    CameraAngle,
    CameraMovement,
    LensFamily,
    LightingMood,
    RuleBasedScenePlanner,
    Scene,
    SceneTransition,
    ShotPurpose,
    ShotSize,
    SSIEValidator,
)


def _scene(**overrides: object) -> Scene:
    scene = Scene(
        scene_id="SCN-010",
        episode_id="EP-001",
        sequence_number=10,
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-MAURITANIA-BRIDGE",
        summary="An alarm signals a threat as James confronts Cheryl on the bridge.",
        participant_asset_ids=("CHR-JAMES", "CHR-CHERYL"),
        dialogue=("Unknown vessel closing fast.", "Hold our position."),
        required_asset_ids=("PROP-BRIDGE-CONSOLE",),
        time_of_day="night",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=42.0,
    )
    return replace(scene, **overrides)


def test_scene_planner_enriches_every_shot() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())

    assert plan.shots
    for shot in plan.shots:
        assert shot.camera_plan is not None
        assert shot.lighting_plan is not None
        assert shot.blocking_plan is not None
        assert shot.continuity_plan is not None


def test_camera_planner_maps_cinematic_intent() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())
    establishing = plan.shots[0]
    reaction = next(shot for shot in plan.shots if shot.purpose is ShotPurpose.REACTION)

    assert establishing.camera_plan is not None
    assert establishing.camera_plan.shot_size is ShotSize.EXTREME_WIDE
    assert establishing.camera_plan.lens_family is LensFamily.WIDE
    assert reaction.camera_plan is not None
    assert reaction.camera_plan.shot_size is ShotSize.CLOSE_UP
    assert reaction.camera_plan.movement is CameraMovement.PUSH_IN


def test_lighting_planner_preserves_scene_continuity_key() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())
    continuity_keys = {
        shot.lighting_plan.continuity_key
        for shot in plan.shots
        if shot.lighting_plan is not None
    }

    assert continuity_keys == {"LOC-MAURITANIA-BRIDGE:night:tense"}
    assert all(
        shot.lighting_plan is not None
        and shot.lighting_plan.mood is LightingMood.TENSE
        for shot in plan.shots
    )


def test_blocking_planner_preserves_eye_lines_and_axis() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())
    master = next(shot for shot in plan.shots if shot.purpose is ShotPurpose.MASTER)
    coverage = next(shot for shot in plan.shots if shot.purpose is ShotPurpose.COVERAGE)

    assert master.blocking_plan is not None
    assert master.blocking_plan.pattern is BlockingPattern.TWO_SHOT
    assert len(master.blocking_plan.subjects) == 2
    assert coverage.camera_plan is not None
    assert coverage.camera_plan.angle is CameraAngle.OVER_SHOULDER
    assert coverage.blocking_plan is not None
    assert "Do not cross" in coverage.blocking_plan.movement_notes[-1]


def test_continuity_planner_links_consecutive_shots() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())
    first = plan.shots[0]
    second = plan.shots[1]

    assert first.continuity_plan is not None
    assert second.continuity_plan is not None
    assert not any(
        "Continue spatial" in requirement
        for requirement in first.continuity_plan.incoming_requirements
    )
    assert any(
        first.shot_id in requirement
        for requirement in second.continuity_plan.incoming_requirements
    )
    assert any(
        "PROP-BRIDGE-CONSOLE" in state
        for state in second.continuity_plan.prop_states
    )


def test_validator_rejects_partial_production_enrichment() -> None:
    plan = RuleBasedScenePlanner().plan_scene(_scene())
    shot = plan.shots[0]
    partial = replace(
        shot,
        lighting_plan=None,
        blocking_plan=None,
        continuity_plan=None,
    )
    invalid_plan = replace(plan, shots=(partial, *plan.shots[1:]))

    result = SSIEValidator().validate_scene_plan(invalid_plan)

    assert result.passed is False
    assert any(
        issue.code == "INCOMPLETE_SHOT_PRODUCTION_PLAN"
        for issue in result.issues
    )
