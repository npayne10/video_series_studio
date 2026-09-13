from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.shots import ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    GovernedShotPlanningService,
    ScenePlanningService,
    StoryLifecycleService,
    StoryService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _planning(tmp_path: Path, *, scene_runtime: int = 60):
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
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
        production_objective="Establish the expedition.",
        target_runtime_seconds=600,
    )
    episodes.mark_ready(episode.episode_id)
    scenes = ScenePlanningService(projects, episodes, StoryService(projects))
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Launch",
        story_scope="Mauritania bridge launch sequence.",
        production_objective="Launch the Mauritania.",
        target_runtime_seconds=scene_runtime,
        setting_requirement="Mauritania bridge",
        required_events=("Mauritania begins its launch sequence",),
    )
    scene = scenes.mark_ready(scene.scene_id)
    shots = GovernedShotPlanningService(projects, scenes, ShotPlanningService(projects))
    return context, projects, shots, scene


def _archive_iron_horizon(
    shots: GovernedShotPlanningService,
    scene_id: str,
) -> tuple:
    legacy = tuple(
        shots.create(
            scene_id=scene_id,
            sequence_number=index,
            title=title,
            narrative_purpose=purpose,
            production_objective="Investigate an anomalous signal.",
            target_runtime_seconds=20,
            required_action=action,
            dialogue_requirement=dialogue,
        )
        for index, (title, purpose, action, dialogue) in enumerate(
            (
                (
                    "Iron Horizon Establishing",
                    "Establish the Iron Horizon in Xorix orbit.",
                    "Show the Iron Horizon and its survey bridge.",
                    "Survey stations ready.",
                ),
                (
                    "Sandra Finds the Signal",
                    "Reveal Sandra isolating a repeating transmission.",
                    "Sandra studies the signal and calls James over.",
                    "Commander, I have something unusual.",
                ),
                (
                    "The Empty Moon",
                    "Establish why the signal should not exist.",
                    "James confirms that the source is the empty moon.",
                    "How unusual?",
                ),
            ),
            start=1,
        )
    )
    archive = shots._archive_scene_plans(
        scene_id,
        legacy,
        metadata={"reason": "legacy-iron-horizon-authority"},
    )
    assert archive is not None
    return legacy


def _write_mauritania_current(
    shots: GovernedShotPlanningService,
    scene_id: str,
) -> tuple:
    shots._write(())
    current = tuple(
        shots.create(
            scene_id=scene_id,
            sequence_number=index,
            title="Mauritania Launch",
            narrative_purpose="Launch the Mauritania from its governed bridge context.",
            production_objective="Begin the Mauritania flight sequence.",
            target_runtime_seconds=20,
            required_action="Keep James and Sandra on the Mauritania bridge during launch.",
            dialogue_requirement=dialogue,
        )
        for index, dialogue in enumerate(
            (
                "Everybody strapped in? Good. Now, lets get this beast to fly.",
                "OK. Here we go!",
                "",
            ),
            start=1,
        )
    )
    return current


def _set_hardware_limit(project_directory: Path, seconds: int) -> None:
    path = (
        project_directory
        / ".vscs"
        / "provider_executions"
        / "hardware_capability.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "capability": {
                    "gpu_name": "Test GPU",
                    "vram_class_gb": 24,
                    "validated_maximum_shot_seconds": seconds,
                }
            }
        ),
        encoding="utf-8",
    )


def test_valid_current_authority_beats_richer_archived_semantics(tmp_path: Path) -> None:
    context, _projects, shots, scene = _planning(tmp_path)
    archived = _archive_iron_horizon(shots, scene.scene_id)
    current = _write_mauritania_current(shots, scene.scene_id)

    assert shots._semantic_density(archived) > shots._semantic_density(current)

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source == "current-governed-plan"
    combined_dialogue = " ".join(shot.dialogue_requirement for shot in proposal.proposed_shots)
    assert "Everybody strapped in?" in combined_dialogue
    assert "OK. Here we go!" in combined_dialogue
    assert "Commander, I have something unusual." not in combined_dialogue
    assert "How unusual?" not in combined_dialogue
    assert all("Iron Horizon" not in shot.title for shot in proposal.proposed_shots)
    context.shutdown()


def test_archive_is_fallback_when_current_authority_is_incomplete(tmp_path: Path) -> None:
    context, _projects, shots, scene = _planning(tmp_path)
    archived = _archive_iron_horizon(shots, scene.scene_id)
    current = _write_mauritania_current(shots, scene.scene_id)
    shots._write((replace(current[0], target_runtime_seconds=7),))

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source.startswith("archived:")
    assert proposal.semantic_source_shot_count == len(archived)
    assert any(
        shot.dialogue_requirement == "Commander, I have something unusual."
        for shot in proposal.proposed_shots
    )
    context.shutdown()


def test_hardware_replan_can_reexpand_only_through_matching_semantic_lineage(
    tmp_path: Path,
) -> None:
    context, projects, shots, scene = _planning(tmp_path, scene_runtime=14)
    original = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Mauritania Launch Command",
        narrative_purpose="Launch the Mauritania under James and Sandra's control.",
        production_objective="Begin the governed flight sequence.",
        target_runtime_seconds=14,
        required_action="James gives the launch command and Sandra initiates flight.",
        dialogue_requirement="Launch the Mauritania now.",
    )

    first = shots.apply_hardware_aware_replan(scene.scene_id)
    assert first.new_shot_count == 2

    unrelated = replace(
        original,
        title="Iron Horizon Signal",
        narrative_purpose="Investigate an unrelated historical signal.",
        production_objective="Investigate the Iron Horizon anomaly.",
        required_action="Sandra studies the Iron Horizon signal.",
        dialogue_requirement="Commander, I have something unusual.",
    )
    unrelated_archive = shots._archive_scene_plans(
        scene.scene_id,
        (unrelated,),
        metadata={"reason": "unrelated-history"},
    )
    assert unrelated_archive is not None

    assert projects.project_directory is not None
    _set_hardware_limit(projects.project_directory, 14)
    proposal = shots.propose_hardware_aware_replan(scene.scene_id)

    assert proposal.semantic_source.startswith("archived:")
    assert proposal.semantic_source_shot_count == 1
    assert proposal.proposed_shot_count == 1
    assert proposal.proposed_shots[0].title.startswith(original.title)
    assert proposal.proposed_shots[0].dialogue_requirement == original.dialogue_requirement
    assert "Iron Horizon" not in proposal.proposed_shots[0].title
    context.shutdown()


def test_repeated_hardware_replanning_does_not_change_semantic_identity(tmp_path: Path) -> None:
    context, projects, shots, scene = _planning(tmp_path, scene_runtime=14)
    original = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Mauritania Launch Command",
        narrative_purpose="Launch the Mauritania under James and Sandra's control.",
        production_objective="Begin the governed flight sequence.",
        target_runtime_seconds=14,
        required_action="James gives the launch command and Sandra initiates flight.",
        dialogue_requirement="Launch the Mauritania now.",
    )

    shots.apply_hardware_aware_replan(scene.scene_id)
    assert projects.project_directory is not None
    _set_hardware_limit(projects.project_directory, 14)
    shots.apply_hardware_aware_replan(scene.scene_id)
    _set_hardware_limit(projects.project_directory, 7)

    proposal = shots.propose_hardware_aware_replan(scene.scene_id)
    combined = " ".join(
        (
            shot.title,
            shot.narrative_purpose,
            shot.required_action,
            shot.dialogue_requirement,
        )
        for shot in proposal.proposed_shots
    )

    assert original.title in combined
    assert original.dialogue_requirement in combined
    assert "Iron Horizon" not in combined
    assert "Commander, I have something unusual." not in combined
    context.shutdown()
