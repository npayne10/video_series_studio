"""Tests for Phase 19.3.3 governed Shot Planning."""

from __future__ import annotations

import json
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


def test_provider_neutral_replan_uses_fifteen_second_cinematic_ceiling(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=180,
    )
    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.maximum_shot_runtime_seconds == 15
    assert proposal.proposed_shot_count == 12
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 180
    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots) <= 15
    assert all(shot.status is ShotPlanStatus.DRAFT for shot in proposal.proposed_shots)
    assert proposal.proposed_shots[0].title.endswith("— Establish")
    assert proposal.proposed_shots[-1].title.endswith("— Resolve")
    assert all(
        "Governed cinematic Shot runtime must not exceed 15 seconds." in shot.shot_constraints
        for shot in proposal.proposed_shots
    )
    context.shutdown()


def test_provider_neutral_replan_archives_previous_governed_authority(
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
    assert result.new_shot_count == 4
    assert result.maximum_shot_runtime_seconds == 15
    assert result.archive_path is not None
    assert result.archive_path.is_file()
    archived = result.archive_path.read_text(encoding="utf-8")
    assert previous.shot_id in archived
    assert "hardware-aware-scene-replan" in archived
    assert '"duration_policy": "provider-neutral-cinematic-v1"' in archived
    current = shots.list_plans(scene_id=scene.scene_id)
    assert len(current) == 4
    assert sum(shot.target_runtime_seconds for shot in current) == 60
    assert all(shot.status is ShotPlanStatus.DRAFT for shot in current)
    context.shutdown()


def test_cinematic_planning_is_decoupled_from_legacy_provider_hardware_ceiling(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(tmp_path)

    capability = shots.hardware_capability()
    accepted = _create(shots, scene.scene_id, runtime=12)

    assert capability["validated_maximum_shot_seconds"] == 7
    assert accepted.target_runtime_seconds == 12
    assert shots.governed_shot_limit_seconds() == 15
    assert shots.hardware_shot_limit_seconds() == 15

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.maximum_shot_runtime_seconds == 15
    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots) <= 15
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    context.shutdown()


def test_semantic_replan_prefers_richer_archived_narrative_authority(
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
    assert proposal.proposed_shot_count == 6
    assert any(shot.title.startswith("Sandra Finds the Signal") for shot in proposal.proposed_shots)
    assert any(
        shot.dialogue_requirement == "Commander, I have something unusual."
        for shot in proposal.proposed_shots
    )
    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots) <= 15
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    context.shutdown()


def test_semantic_decomposition_preserves_each_source_beat_without_dialogue_duplication(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=30,
    )
    source = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Sandra Reports the Pattern",
        narrative_purpose="Let Sandra explain the repeating signal.",
        production_objective="Move the mystery into active investigation.",
        target_runtime_seconds=30,
        required_action="Sandra turns from the display and reports the forty-seven second pattern.",
        dialogue_requirement="Commander, I have something unusual.",
        continuity_in="Sandra is already studying the signal.",
        continuity_out="James moves toward her station.",
    )

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source == "current-governed-plan"
    assert proposal.proposed_shot_count == 2
    first, second = proposal.proposed_shots
    assert first.target_runtime_seconds == 15
    assert second.target_runtime_seconds == 15
    assert first.title == f"{source.title} — Establish"
    assert second.title == f"{source.title} — Resolve"
    assert first.continuity_in == source.continuity_in
    assert second.continuity_out == source.continuity_out
    assert [shot.dialogue_requirement for shot in proposal.proposed_shots].count(
        source.dialogue_requirement
    ) == 1
    assert "reports" not in first.required_action.casefold()
    assert "reports" in second.required_action.casefold()
    context.shutdown()


def test_semantic_cinematic_coverage_assigns_distinct_editorial_roles(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    source = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Weak Repeating Signal",
        narrative_purpose="Convey Sandra's analysis of the repeating transmission.",
        production_objective="Establish that the signal comes from the outer moon.",
        target_runtime_seconds=60,
        required_action=(
            "Sandra studies the repeating signal while James follows her analysis "
            "and the display shows the forty-seven second pattern."
        ),
        dialogue_requirement="Commander, I have something unusual.",
    )

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)
    children = proposal.proposed_shots

    assert len(children) == 4
    assert [shot.target_runtime_seconds for shot in children] == [15, 15, 15, 15]
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
    assert "Do not depict or imply spoken dialogue" in children[2].required_action
    assert source.required_action not in children[2].required_action
    assert [shot.dialogue_requirement for shot in children].count(source.dialogue_requirement) == 1
    assert all(
        f"Cinematic coverage role: {shot.coverage_role.value}." in shot.shot_constraints
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


def test_two_shot_semantic_beat_carries_dialogue_on_resolve_child(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=30,
    )
    source = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Sandra Reports",
        narrative_purpose="Sandra reports the anomaly.",
        production_objective="Move the investigation forward.",
        target_runtime_seconds=30,
        required_action="Sandra turns from the display and reports the signal.",
        dialogue_requirement="Commander, I have something unusual.",
    )

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)
    first, second = proposal.proposed_shots

    assert first.coverage_role is CinematicCoverageRole.ESTABLISHING
    assert second.coverage_role is CinematicCoverageRole.RESOLVE
    assert first.dialogue_requirement == ""
    assert second.dialogue_requirement == source.dialogue_requirement
    assert [shot.dialogue_requirement for shot in proposal.proposed_shots].count(
        source.dialogue_requirement
    ) == 1
    context.shutdown()


def test_production_aware_replan_preserves_produced_prefix_and_regenerates_only_future_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    semantic = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Signal Discovery",
        narrative_purpose="Reveal Sandra's discovery and James's response.",
        production_objective="Advance the anomaly investigation.",
        target_runtime_seconds=60,
        required_action=(
            "Sandra studies the signal, reports something unusual to James, "
            "and James turns toward her station."
        ),
        dialogue_requirement="Commander, I have something unusual.",
    )

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 7)
    first_replan = shots.apply_hardware_aware_replan(scene.scene_id)
    assert len(first_replan.shots) == 9

    current = list(shots.list_plans(scene_id=scene.scene_id))
    stale_future = replace(
        current[2],
        required_action=(
            "Show a specific information-bearing visual detail that advances: "
            f"{semantic.required_action} Do not repeat the master view."
        ),
    )
    current[2] = stale_future
    shots._write(tuple(current))

    project = tmp_path / "Demo"
    boundary_path = project / ".vscs" / "governed_shot_boundaries.json"
    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    boundary_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "boundaries": [{"shot_id": current[0].shot_id, "status": "published"}],
            }
        ),
        encoding="utf-8",
    )
    acceptance_path = project / ".vscs" / "timed_span_acceptance.json"
    acceptance_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "assemblies": [{"shot_id": current[1].shot_id}],
                "qc_records": [],
                "qc_invalidations": [],
                "assembly_invalidations": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 15)
    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert [item.shot_id for item in proposal.protected_shots] == [
        current[0].shot_id,
        current[1].shot_id,
    ]
    assert proposal.maximum_shot_runtime_seconds == 15
    assert proposal.proposed_shots[0] == current[0]
    assert proposal.proposed_shots[1] == current[1]
    assert proposal.proposed_shots[2].shot_id == stale_future.shot_id
    assert proposal.proposed_shots[2].required_action != stale_future.required_action
    assert proposal.regenerated_shot_count == len(proposal.proposed_shots) - 2
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    assert max(shot.target_runtime_seconds for shot in proposal.proposed_shots[2:]) <= 15
    assert all(not shot.dialogue_requirement for shot in proposal.proposed_shots[2:])
    assert all(
        "reports" not in shot.required_action.casefold() for shot in proposal.proposed_shots[2:]
    )

    result = shots.apply_hardware_aware_replan(scene.scene_id)
    persisted = shots.list_plans(scene_id=scene.scene_id)
    assert result.shots == persisted
    assert persisted[0] == current[0]
    assert persisted[1] == current[1]
    assert persisted[2:] == proposal.proposed_shots[2:]
    context.shutdown()


def test_production_aware_replan_recovers_lineage_across_accepted_produced_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    semantic = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Signal Discovery",
        narrative_purpose="Reveal Sandra's discovery and James's response.",
        production_objective="Advance the anomaly investigation.",
        target_runtime_seconds=60,
        required_action=(
            "Sandra studies the signal, reports something unusual to James, "
            "and James turns toward her station."
        ),
        dialogue_requirement="Commander, I have something unusual.",
    )

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 7)
    first_replan = shots.apply_hardware_aware_replan(scene.scene_id)
    assert len(first_replan.shots) == 9

    current = list(shots.list_plans(scene_id=scene.scene_id))
    accepted_second = replace(
        current[1],
        title="Signal Discovery — Accepted Production Override",
        shot_constraints=tuple(
            constraint
            for constraint in current[1].shot_constraints
            if not constraint.startswith("Preserve semantic source Shot ")
        ),
    )
    stale_future = replace(
        current[2],
        required_action=(
            "Show a specific information-bearing visual detail that advances: "
            f"{semantic.required_action} Do not repeat the master view."
        ),
    )
    current[1] = accepted_second
    current[2] = stale_future
    shots._write(tuple(current))

    project = tmp_path / "Demo"
    boundary_path = project / ".vscs" / "governed_shot_boundaries.json"
    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    boundary_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "boundaries": [{"shot_id": current[0].shot_id, "status": "published"}],
            }
        ),
        encoding="utf-8",
    )
    acceptance_path = project / ".vscs" / "timed_span_acceptance.json"
    acceptance_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "assemblies": [{"shot_id": accepted_second.shot_id}],
                "qc_records": [],
                "qc_invalidations": [],
                "assembly_invalidations": [],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 15)
    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source.startswith("archived:")
    assert [item.shot_id for item in proposal.protected_shots] == [
        current[0].shot_id,
        accepted_second.shot_id,
    ]
    assert proposal.proposed_shots[0] == current[0]
    assert proposal.proposed_shots[1] == accepted_second
    assert proposal.proposed_shots[2].shot_id == stale_future.shot_id
    assert proposal.proposed_shots[2].required_action != stale_future.required_action
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    assert all(not shot.dialogue_requirement for shot in proposal.proposed_shots[2:])
    context.shutdown()


def test_replan_recovers_unique_archive_from_partial_surviving_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    semantic = (
        shots.create(
            scene_id=scene.scene_id,
            sequence_number=1,
            title="First Semantic Beat",
            narrative_purpose="Establish the first half of the Scene.",
            production_objective="Advance the first semantic beat.",
            target_runtime_seconds=30,
            required_action="James studies the first anomaly.",
        ),
        shots.create(
            scene_id=scene.scene_id,
            sequence_number=2,
            title="Second Semantic Beat",
            narrative_purpose="Resolve the second half of the Scene.",
            production_objective="Advance the second semantic beat.",
            target_runtime_seconds=30,
            required_action="Sandra isolates the second anomaly.",
        ),
    )

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 7)
    first = shots.apply_hardware_aware_replan(scene.scene_id)
    assert len(first.shots) == 10

    current = list(shots.list_plans(scene_id=scene.scene_id))
    first_marker = f"Preserve semantic source Shot {semantic[0].shot_id}: {semantic[0].title}."
    for index in range(5):
        current[index] = replace(
            current[index],
            title=f"Accepted Override {index + 1:03d}",
            shot_constraints=tuple(
                constraint
                for constraint in current[index].shot_constraints
                if constraint != first_marker
            ),
        )
    shots._write(tuple(current))

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 15)
    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source.startswith("archived:")
    assert proposal.semantic_source_shot_count == 2
    assert proposal.proposed_shot_count == 4
    assert sum(shot.target_runtime_seconds for shot in proposal.proposed_shots) == 60
    context.shutdown()


def test_replan_fails_closed_when_hardware_decomposition_has_no_lineage_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=30,
    )
    shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Signal Discovery",
        narrative_purpose="Reveal the signal.",
        production_objective="Advance the investigation.",
        target_runtime_seconds=30,
        required_action="Sandra studies the signal while James observes.",
    )

    monkeypatch.setattr(shots, "governed_shot_limit_seconds", lambda: 7)
    shots.apply_hardware_aware_replan(scene.scene_id)
    current = list(shots.list_plans(scene_id=scene.scene_id))
    for index, plan in enumerate(current):
        current[index] = replace(
            plan,
            shot_constraints=tuple(
                constraint
                for constraint in plan.shot_constraints
                if not constraint.startswith("Preserve semantic source Shot ")
            ),
        )
    shots._write(tuple(current))

    with pytest.raises(
        GovernedShotPlanningError,
        match="no recoverable semantic lineage",
    ):
        shots.propose_hardware_aware_replan(scene.scene_id)
    context.shutdown()


def test_replan_recovers_scene_fallback_lineage_when_no_archive_exists(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=30,
    )

    first = shots.apply_hardware_aware_replan(scene.scene_id)
    assert len(first.shots) == 2
    assert first.archive_path is None

    second = shots.propose_hardware_aware_replan(scene.scene_id)

    assert second.semantic_source == "scene-authority-fallback-lineage"
    assert second.proposed_shot_count == 2
    assert sum(shot.target_runtime_seconds for shot in second.proposed_shots) == 30
    context.shutdown()


def test_replan_fails_closed_when_hardware_lineage_authority_cannot_be_recovered(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    plan = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Unrecoverable Beat — Progression",
        narrative_purpose="Represent a deliberately invalid lineage case.",
        production_objective="Prove fail-closed lineage recovery.",
        target_runtime_seconds=60,
        required_action="Hold the invalid test beat.",
        shot_constraints=(
            "Cinematic coverage role: progression.",
            "Preserve semantic source Shot EP-001-SCN-001-SHT-999: Missing Authority.",
        ),
    )
    shots._write((replace(plan, coverage_role=CinematicCoverageRole.PROGRESSION),))

    with pytest.raises(
        GovernedShotPlanningError,
        match="semantic source authority cannot be recovered",
    ):
        shots.propose_hardware_aware_replan(scene.scene_id)
    context.shutdown()


def test_production_aware_replan_fails_closed_for_noncontiguous_produced_shots(
    tmp_path: Path,
) -> None:
    context, _episodes, _scenes, shots, _legacy, scene = _planning(
        tmp_path,
        scene_runtime=60,
    )
    shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Signal Discovery",
        narrative_purpose="Reveal the signal.",
        production_objective="Advance the investigation.",
        target_runtime_seconds=60,
        required_action="Sandra studies the signal while James observes.",
    )
    shots.apply_hardware_aware_replan(scene.scene_id)
    current = shots.list_plans(scene_id=scene.scene_id)
    assert len(current) == 4

    project = tmp_path / "Demo"
    boundary_path = project / ".vscs" / "governed_shot_boundaries.json"
    boundary_path.parent.mkdir(parents=True, exist_ok=True)
    boundary_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "boundaries": [{"shot_id": current[1].shot_id, "status": "published"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        GovernedShotPlanningError,
        match="do not form a contiguous prefix",
    ):
        shots.propose_hardware_aware_replan(scene.scene_id)
    context.shutdown()

