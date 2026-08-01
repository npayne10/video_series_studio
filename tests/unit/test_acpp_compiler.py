"""Tests for deterministic SSIE-to-ACPP compilation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from vscs.application.acpp import (
    ACPPCompilationError,
    ACPPCompilerConfig,
    AssetBindingRole,
    RenderQualityMode,
    SSIEToACPPCompiler,
)
from vscs.application.ssie import (
    ProductionPlan,
    RuleBasedScenePlanner,
    Scene,
    SceneTransition,
)


def _production_plan() -> ProductionPlan:
    scene = Scene(
        scene_id="SCN-002",
        episode_id="EP-001",
        sequence_number=2,
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-MAURITANIA-BRIDGE",
        summary="James confronts Cheryl as an alarm warns of an approaching vessel.",
        participant_asset_ids=("CHR-JAMES", "CHR-CHERYL"),
        dialogue=("We hold position.", "That may no longer be possible."),
        required_asset_ids=("PROP-BRIDGE-CONSOLE",),
        time_of_day="night",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=42.0,
    )
    scene_plan = RuleBasedScenePlanner().plan_scene(scene)
    return ProductionPlan(
        production_id="PROD-XORIX-S01E01",
        episode_id="EP-001",
        scene_plans=(scene_plan,),
    )


def test_compiler_creates_one_package_per_shot_in_order() -> None:
    plan = _production_plan()

    packages = SSIEToACPPCompiler().compile(plan)

    assert len(packages) == len(plan.scene_plans[0].shots)
    assert [package.identity.shot_id for package in packages] == [
        shot.shot_id for shot in plan.scene_plans[0].shots
    ]
    assert packages[0].identity.clip_id.endswith("SC002-SH001-CL001")
    assert packages[-1].identity.clip_id.endswith(
        f"SC002-SH{len(packages):03d}-CL001"
    )


def test_compiler_converts_duration_to_frames() -> None:
    plan = _production_plan()
    shot = plan.scene_plans[0].shots[0]

    package = SSIEToACPPCompiler().compile(plan)[0]

    assert shot.estimated_duration_seconds is not None
    assert package.render.frame_count == round(shot.estimated_duration_seconds * 24)
    assert package.render.frames_per_second == 24


def test_compiler_maps_assets_and_production_intent() -> None:
    package = SSIEToACPPCompiler().compile(_production_plan())[0]
    bindings = {binding.asset_id: binding.role for binding in package.assets}

    assert bindings["LOC-MAURITANIA-BRIDGE"] is AssetBindingRole.LOCATION
    assert "extreme_wide" in package.prompt.camera_language
    assert "tense" in package.prompt.lighting_intent
    assert package.prompt.environment_intent == "INT. MAURITANIA BRIDGE - NIGHT"
    assert package.metadata["source"] == "ssie"


def test_compiler_chains_clip_dependencies_and_continuity() -> None:
    packages = SSIEToACPPCompiler().compile(_production_plan())

    assert packages[0].dependencies == ()
    assert packages[0].continuity.incoming_clip_id is None
    for previous, current in zip(packages, packages[1:], strict=True):
        assert current.dependencies == (previous.identity.clip_id,)
        assert current.continuity.incoming_clip_id == previous.identity.clip_id


def test_compiler_uses_custom_render_defaults() -> None:
    compiler = SSIEToACPPCompiler(
        ACPPCompilerConfig(
            width=1280,
            height=720,
            frames_per_second=30,
            quality_mode=RenderQualityMode.PREVIEW,
            output_root="renders/preview",
        )
    )

    package = compiler.compile(_production_plan())[0]

    assert package.render.width == 1280
    assert package.render.height == 720
    assert package.render.frames_per_second == 30
    assert package.render.quality_mode is RenderQualityMode.PREVIEW
    assert package.output.relative_directory.startswith("renders/preview/")


def test_compiler_rejects_incomplete_ssie_shot() -> None:
    plan = _production_plan()
    scene_plan = plan.scene_plans[0]
    incomplete = replace(scene_plan.shots[0], camera_plan=None)
    invalid_scene_plan = replace(
        scene_plan,
        shots=(incomplete, *scene_plan.shots[1:]),
    )
    invalid_plan = replace(plan, scene_plans=(invalid_scene_plan,))

    with pytest.raises(ACPPCompilationError, match="missing camera"):
        SSIEToACPPCompiler().compile(invalid_plan)
