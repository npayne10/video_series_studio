"""Tests for Phase 19.3.3 governed Shot Planning."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    GovernedShotPlanningError,
    GovernedShotPlanningService,
    ScenePlanningService,
    ShotPlanStatus,
    StoryLifecycleService,
    StoryService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _planning(tmp_path: Path, *, ready_scene: bool = True, scene_runtime: int = 60):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = StoryLifecycleService(projects)
    story = lifecycle.create_story(title="Xorix")
    episodes = EpisodePlanningService(projects, lifecycle)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival",
        story_scope="Arrival in orbit.",
        production_objective="Establish Xorix.",
        target_runtime_seconds=600,
    )
    episode = episodes.mark_ready(episode.episode_id)
    scenes = ScenePlanningService(projects, episodes, StoryService(projects))
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania settles into orbit.",
        production_objective="Establish planetary scale.",
        target_runtime_seconds=scene_runtime,
        setting_requirement="Xorix orbit",
        required_events=("Xorix fills the forward view",),
    )
    if ready_scene:
        scene = scenes.mark_ready(scene.scene_id)
    legacy = ShotPlanningService(projects)
    shots = GovernedShotPlanningService(projects, scenes, legacy)
    return context, episodes, scenes, shots, legacy, scene


def _create(
    shots: GovernedShotPlanningService,
    scene_id: str,
    *,
    sequence: int = 1,
    runtime: int = 5,
):
    return shots.create(
        scene_id=scene_id,
        sequence_number=sequence,
        title="Reveal Xorix",
        narrative_purpose="Reveal the scale and beauty of Xorix.",
        production_objective="Orient the audience before orbital operations begin.",
        target_runtime_seconds=runtime,
        required_action="Mauritania crosses frame as Xorix dominates the background.",
        dialogue_requirement="No dialogue.",
        continuity_in="The ship has just completed transit.",
        continuity_out="Cut inside to bridge reaction.",
        shot_constraints=("Motion must remain physically plausible.",),
    )


def test_governed_shot_plan_persists_only_shot_level_intent(tmp_path: Path) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(tmp_path)
    shot = _create(shots, scene.scene_id)

    assert shot.shot_id == "EP-001-SCN-001-SHT-001"
    assert shot.status is ShotPlanStatus.DRAFT
    assert shot.narrative_purpose.startswith("Reveal the scale")
    assert shots.plan(shot.shot_id) == shot
    assert shots.list_plans(scene_id=scene.scene_id) == (shot,)
    context.shutdown()


def test_shot_planning_requires_current_ready_scene(tmp_path: Path) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        ready_scene=False,
    )
    with pytest.raises(GovernedShotPlanningError, match="Ready Scene Plan"):
        _create(shots, scene.scene_id)
    context.shutdown()


def test_shot_runtime_budget_cannot_exceed_scene_target(tmp_path: Path) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=10,
    )
    _create(shots, scene.scene_id, sequence=1, runtime=7)
    assert shots.remaining_runtime_seconds(scene.scene_id) == 3
    with pytest.raises(GovernedShotPlanningError, match="runtime exceeds"):
        _create(shots, scene.scene_id, sequence=2, runtime=4)
    second = _create(shots, scene.scene_id, sequence=2, runtime=3)
    assert second.shot_id.endswith("SHT-002")
    assert shots.remaining_runtime_seconds(scene.scene_id) == 0
    context.shutdown()


def test_ready_shot_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(tmp_path)
    shot = shots.mark_ready(_create(shots, scene.scene_id).shot_id)
    assert shots.is_production_ready(shot)

    with pytest.raises(GovernedShotPlanningError, match="return to Draft"):
        shots.delete(shot.shot_id)
    draft = shots.return_to_draft(shot.shot_id)
    assert draft.status is ShotPlanStatus.DRAFT
    context.shutdown()


def test_scene_change_marks_shot_stale_until_reviewed(tmp_path: Path) -> None:
    context, _episodes, scenes, shots, _legacy, scene = _planning(tmp_path)
    shot = shots.mark_ready(_create(shots, scene.scene_id).shot_id)
    assert shots.is_production_ready(shot)

    draft_scene = scenes.return_to_draft(scene.scene_id)
    updated_scene = scenes.update(
        draft_scene.scene_id,
        title=draft_scene.title,
        story_scope=draft_scene.story_scope,
        production_objective=draft_scene.production_objective,
        target_runtime_seconds=draft_scene.target_runtime_seconds,
        setting_requirement=draft_scene.setting_requirement,
        required_events=draft_scene.required_events,
        continuity_in=draft_scene.continuity_in,
        continuity_out="Bridge reaction follows immediately.",
        scene_constraints=draft_scene.scene_constraints,
    )
    scenes.mark_ready(updated_scene.scene_id)

    stale = shots.plan(shot.shot_id)
    assert stale is not None
    assert not shots.is_upstream_current(stale)
    assert not shots.is_production_ready(stale)
    context.shutdown()


def test_legacy_shots_remain_visible_but_outside_governed_storage(tmp_path: Path) -> None:
    context, _episodes, _scenes, shots, legacy, scene = _planning(tmp_path)
    legacy.save_shot(
        ProductionShot(
            shot_id=f"{scene.scene_id}-SHT-007",
            scene_id=scene.scene_id,
            sequence_number=7,
            title="Legacy reveal",
            description="Old Phase 17 shot with camera and lighting choices.",
            estimated_duration_seconds=5.0,
        )
    )

    references = shots.legacy_shots_for_scene(scene.scene_id)
    assert len(references) == 1
    assert references[0].shot_id.endswith("SHT-007")
    assert shots.list_plans(scene_id=scene.scene_id) == ()
    context.shutdown()
