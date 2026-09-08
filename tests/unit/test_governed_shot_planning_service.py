"""Tests for Phase 19.3.3 governed Shot Planning."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.story import (
    CinematicCoverageRole,
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


def test_hardware_aware_replan_covers_full_scene_with_short_governed_shots(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=180,
    )
    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.maximum_shot_runtime_seconds == 7
    assert proposal.proposed_shot_count == 26
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 180
    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots) <= 7
    assert all(shot.status is ShotPlanStatus.DRAFT for shot in proposal.proposed_shots)
    assert proposal.proposed_shots[0].title.endswith("— Establish")
    assert proposal.proposed_shots[-1].title.endswith("— Resolve")
    context.shutdown()


def test_hardware_aware_replan_archives_previous_governed_authority(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    previous = _create(shots, scene.scene_id, runtime=5)
    shots.mark_ready(previous.shot_id)

    result = shots.apply_hardware_aware_replan(scene.scene_id)

    assert result.previous_shot_count == 1
    assert result.new_shot_count == 9
    assert result.archive_path is not None
    assert result.archive_path.is_file()
    archived = result.archive_path.read_text(encoding="utf-8")
    assert previous.shot_id in archived
    assert "hardware-aware-scene-replan" in archived
    current = shots.list_plans(scene_id=scene.scene_id)
    assert len(current) == 9
    assert sum(shot.target_runtime_seconds for shot in current) == 60
    assert all(shot.status is ShotPlanStatus.DRAFT for shot in current)
    context.shutdown()


def test_existing_or_accepted_long_shot_authority_can_be_replanned_for_hardware(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(tmp_path)

    accepted = _create(shots, scene.scene_id, runtime=8)
    assert accepted.target_runtime_seconds == 8

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots) <= 7
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    context.shutdown()


def test_semantic_hardware_replan_prefers_richer_archived_narrative_authority(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    semantic = (
        shots.create(
            scene_id=scene.scene_id,
            sequence_number=1,
            title="Bridge and Xorix",
            narrative_purpose="Establish the bridge and Xorix in orbit.",
            production_objective="Orient the audience.",
            target_runtime_seconds=20,
            required_action="Show the bridge team with Xorix beyond the forward display.",
        ),
        shots.create(
            scene_id=scene.scene_id,
            sequence_number=2,
            title="Sandra Finds the Signal",
            narrative_purpose="Reveal Sandra isolating a weak repeating transmission.",
            production_objective="Introduce the anomaly.",
            target_runtime_seconds=20,
            required_action="Sandra studies the signal and calls James over.",
            dialogue_requirement="Commander, I have something unusual.",
        ),
        shots.create(
            scene_id=scene.scene_id,
            sequence_number=3,
            title="The Empty Moon",
            narrative_purpose="Establish why the signal should not exist.",
            production_objective="End on the contradiction.",
            target_runtime_seconds=20,
            required_action="James confirms the source is the supposedly empty moon.",
        ),
    )
    archive = shots._archive_scene_plans(
        scene.scene_id,
        semantic,
        metadata={"reason": "pre-hardware-semantic-authority"},
    )
    assert archive is not None

    generic = tuple(
        replace(
            item,
            shot_id=f"{scene.scene_id}-SHT-{index:03d}",
            sequence_number=index,
            title=f"Story Beat {index:03d}",
            narrative_purpose="Advance the Scene story.",
            required_action="Show the required story event.",
            target_runtime_seconds=7 if index < 9 else 4,
            dialogue_requirement="",
        )
        for index, item in enumerate(
            (semantic * 3)[:9],
            start=1,
        )
    )
    shots._write(generic)

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source.startswith("archived:")
    assert proposal.semantic_source_shot_count == 3
    assert proposal.proposed_shot_count == 9
    assert any(shot.title.startswith("Sandra Finds the Signal") for shot in proposal.proposed_shots)
    assert any(
        shot.dialogue_requirement == "Commander, I have something unusual."
        for shot in proposal.proposed_shots
    )
    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots) <= 7
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    context.shutdown()


def test_semantic_decomposition_preserves_each_source_beat_without_dialogue_duplication(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=14,
    )
    source = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Sandra Reports the Pattern",
        narrative_purpose="Let Sandra explain the repeating signal.",
        production_objective="Move the mystery into active investigation.",
        target_runtime_seconds=14,
        required_action="Sandra turns from the display and reports the forty-seven second pattern.",
        dialogue_requirement="Commander, I have something unusual.",
        continuity_in="Sandra is already studying the signal.",
        continuity_out="James moves toward her station.",
    )

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source == "current-governed-plan"
    assert proposal.proposed_shot_count == 2
    first, second = proposal.proposed_shots
    assert first.title == f"{source.title} — Establish"
    assert second.title == f"{source.title} — Resolve"
    assert first.continuity_in == source.continuity_in
    assert second.continuity_out == source.continuity_out
    assert [shot.dialogue_requirement for shot in proposal.proposed_shots].count(
        source.dialogue_requirement
    ) == 1
    context.shutdown()


def test_semantic_cinematic_coverage_assigns_distinct_editorial_roles(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=28,
    )
    source = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Weak Repeating Signal",
        narrative_purpose="Convey Sandra's analysis of the repeating transmission.",
        production_objective="Establish that the signal comes from the outer moon.",
        target_runtime_seconds=28,
        required_action=(
            "Sandra studies the repeating signal while James follows her analysis "
            "and the display shows the forty-seven second pattern."
        ),
        dialogue_requirement="Commander, I have something unusual.",
    )

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)
    children = proposal.proposed_shots

    assert len(children) == 4
    assert [shot.coverage_role for shot in children] == [
        CinematicCoverageRole.ESTABLISHING,
        CinematicCoverageRole.DIALOGUE_DELIVERY,
        CinematicCoverageRole.DETAIL_INSERT,
        CinematicCoverageRole.RESOLVE,
    ]
    assert children[0].title == f"{source.title} — Establish"
    assert children[1].title == f"{source.title} — Dialogue"
    assert children[2].title == f"{source.title} — Detail"
    assert children[3].title == f"{source.title} — Resolve"
    assert len({shot.required_action for shot in children}) == 4
    assert "Do not invent additional spoken content" in children[1].required_action
    assert "information-bearing visual detail" in children[2].required_action
    assert [shot.dialogue_requirement for shot in children].count(
        source.dialogue_requirement
    ) == 1
    assert all(
        f"Cinematic coverage role: {shot.coverage_role.value}."
        in shot.shot_constraints
        for shot in children
    )
    context.shutdown()


def test_semantic_cinematic_coverage_persists_role_backward_compatibly(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=7,
    )
    created = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Single Beat",
        narrative_purpose="Advance one compact beat.",
        production_objective="Keep the beat concise.",
        target_runtime_seconds=7,
        required_action="James crosses to Sandra's station.",
    )

    assert created.coverage_role is CinematicCoverageRole.UNSPECIFIED

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)
    assert proposal.proposed_shots[0].coverage_role is CinematicCoverageRole.PROGRESSION

    shots.apply_hardware_aware_replan(scene.scene_id)
    restored = shots.list_plans(scene_id=scene.scene_id)[0]
    assert restored.coverage_role is CinematicCoverageRole.PROGRESSION
    context.shutdown()
