"""Unit tests for Phase 12.1 SSIE foundation."""

from __future__ import annotations

import pytest

from vscs.application.ssie import (
    ProductionPlanBuilder,
    Scene,
    ScenePlan,
    ShotPlan,
    ShotPurpose,
    SSIEBuildError,
    SSIEValidator,
)


class StubScenePlanner:
    def plan_scene(self, scene: Scene) -> ScenePlan:
        shot = ShotPlan(
            shot_id=f"{scene.scene_id}-SH001",
            scene_id=scene.scene_id,
            sequence_number=1,
            purpose=ShotPurpose.ESTABLISHING,
            description="Establish the location and participants.",
            subject_asset_ids=scene.participant_asset_ids,
            required_asset_ids=(scene.location_asset_id,),
            estimated_duration_seconds=6.0,
        )
        return ScenePlan(
            scene=scene,
            objective="Establish the scene context.",
            emotional_intent="Controlled anticipation.",
            shots=(shot,),
        )


def make_scene(sequence_number: int = 1) -> Scene:
    return Scene(
        scene_id=f"SC{sequence_number:03d}",
        episode_id="EP001",
        sequence_number=sequence_number,
        heading="INT. COMMAND DECK - DAY",
        location_asset_id="LOC-GUILD-001",
        summary="The command team prepares for departure.",
        participant_asset_ids=("CHR-COMMANDER-001",),
        estimated_duration_seconds=30.0,
    )


def test_scene_plan_validation_accepts_contiguous_shots() -> None:
    scene_plan = StubScenePlanner().plan_scene(make_scene())

    result = SSIEValidator().validate_scene_plan(scene_plan)

    assert result.passed
    assert result.issues == []


def test_scene_plan_validation_rejects_scene_mismatch() -> None:
    scene = make_scene()
    invalid_shot = ShotPlan(
        shot_id="SC999-SH001",
        scene_id="SC999",
        sequence_number=1,
        purpose=ShotPurpose.MASTER,
        description="Invalid scene assignment.",
    )
    plan = ScenePlan(
        scene=scene,
        objective="Test validation.",
        emotional_intent="Neutral.",
        shots=(invalid_shot,),
    )

    result = SSIEValidator().validate_scene_plan(plan)

    assert not result.passed
    assert any(issue.code == "SHOT_SCENE_MISMATCH" for issue in result.issues)


def test_builder_orders_scenes_and_counts_shots() -> None:
    builder = ProductionPlanBuilder(StubScenePlanner())

    plan = builder.build(
        production_id="PROD-001",
        episode_id="EP001",
        scenes=(make_scene(2), make_scene(1)),
    )

    assert [item.scene.sequence_number for item in plan.scene_plans] == [1, 2]
    assert plan.shot_count == 2


def test_builder_rejects_empty_production() -> None:
    builder = ProductionPlanBuilder(StubScenePlanner())

    with pytest.raises(SSIEBuildError) as error:
        builder.build(
            production_id="PROD-001",
            episode_id="EP001",
            scenes=(),
        )

    assert any(issue.code == "PRODUCTION_HAS_NO_SCENES" for issue in error.value.issues)
