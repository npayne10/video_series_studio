"""Tests for the Phase 19.3.2 Scene Planner service."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    EpisodePlanningService,
    ScenePlanningError,
    ScenePlanningService,
    ScenePlanStatus,
    StoryLifecycleService,
)
from vscs.bootstrap import (
    ApplicationContext,
    BootstrapOptions,
    StartupMode,
    build_application_context,
)


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


def _services(
    tmp_path: Path,
    *,
    episode_runtime: int = 2700,
    ready: bool = True,
) -> tuple[ApplicationContext, EpisodePlanningService, ScenePlanningService, str]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    story = stories.create_story(title="Xorix")
    episodes = EpisodePlanningService(projects, stories)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival at Xorix",
        story_scope="Arrival in orbit through landing.",
        production_objective="Establish Xorix and move the crew into first contact.",
        target_runtime_seconds=episode_runtime,
        continuity_in="Mauritania completes interstellar transit.",
        continuity_out="The landing party is ready for first contact.",
        production_constraints=("Keep spacecraft motion physically plausible.",),
    )
    if ready:
        episode = episodes.mark_ready(episode.episode_id)
    return context, episodes, ScenePlanningService(projects, episodes), episode.episode_id


def _create(
    service: ScenePlanningService, episode_id: str, *, sequence: int = 1, runtime: int = 300
):
    return service.create(
        episode_id=episode_id,
        sequence_number=sequence,
        title="Orbital Arrival",
        story_scope="Mauritania establishes orbit around Xorix.",
        production_objective="Establish planetary scale and controlled orbital arrival.",
        target_runtime_seconds=runtime,
        setting_requirement="Xorix orbit with Mauritania approaching the planet.",
        required_events=(
            "Xorix fills the forward view.",
            "Mauritania settles into controlled orbit.",
        ),
        continuity_in="The ship has just emerged from interstellar transit.",
        continuity_out="The crew begins descent preparations.",
        scene_constraints=("Orbital motion must remain physically plausible.",),
    )


def test_scene_plan_persists_only_scene_level_production_intent(tmp_path: Path) -> None:
    context, _episodes, service, episode_id = _services(tmp_path)
    scene = _create(service, episode_id)

    assert scene.scene_id == "EP-001-SCN-001"
    assert scene.episode_id == episode_id
    assert scene.status is ScenePlanStatus.DRAFT
    assert scene.required_events == (
        "Xorix fills the forward view.",
        "Mauritania settles into controlled orbit.",
    )
    assert service.plan(scene.scene_id) == scene
    assert service.list_plans(episode_id=episode_id) == (scene,)
    context.shutdown()


def test_scene_planning_requires_a_ready_episode(tmp_path: Path) -> None:
    context, _episodes, service, episode_id = _services(tmp_path, ready=False)

    with pytest.raises(ScenePlanningError, match="Ready Episode Plan"):
        _create(service, episode_id)
    context.shutdown()


def test_scene_runtime_budget_cannot_exceed_episode_target(tmp_path: Path) -> None:
    context, _episodes, service, episode_id = _services(tmp_path, episode_runtime=600)
    _create(service, episode_id, sequence=1, runtime=400)

    assert service.allocated_runtime_seconds(episode_id) == 400
    assert service.remaining_runtime_seconds(episode_id) == 200
    with pytest.raises(ScenePlanningError, match="runtime exceeds"):
        _create(service, episode_id, sequence=2, runtime=201)
    second = _create(service, episode_id, sequence=2, runtime=200)
    assert second.scene_id == "EP-001-SCN-002"
    assert service.remaining_runtime_seconds(episode_id) == 0
    context.shutdown()


def test_scene_constraints_inherit_episode_constraints_without_duplication(tmp_path: Path) -> None:
    context, _episodes, service, episode_id = _services(tmp_path)
    scene = _create(service, episode_id)

    assert scene.scene_constraints == ("Orbital motion must remain physically plausible.",)
    assert service.effective_constraints(scene) == (
        "Keep spacecraft motion physically plausible.",
        "Orbital motion must remain physically plausible.",
    )
    context.shutdown()


def test_ready_scene_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    context, _episodes, service, episode_id = _services(tmp_path)
    scene = service.mark_ready(_create(service, episode_id).scene_id)

    assert service.is_production_ready(scene)
    with pytest.raises(ScenePlanningError, match="return to Draft"):
        service.update(
            scene.scene_id,
            title="Changed",
            story_scope=scene.story_scope,
            production_objective=scene.production_objective,
            target_runtime_seconds=scene.target_runtime_seconds,
            setting_requirement=scene.setting_requirement,
            required_events=scene.required_events,
            continuity_in=scene.continuity_in,
            continuity_out=scene.continuity_out,
            scene_constraints=scene.scene_constraints,
        )
    with pytest.raises(ScenePlanningError, match="return to Draft"):
        service.delete(scene.scene_id)

    draft = service.return_to_draft(scene.scene_id)
    assert draft.status is ScenePlanStatus.DRAFT
    context.shutdown()


def test_episode_change_marks_existing_scene_stale_until_reviewed(tmp_path: Path) -> None:
    context, episodes, service, episode_id = _services(tmp_path)
    scene = service.mark_ready(_create(service, episode_id).scene_id)
    assert service.is_production_ready(scene)

    episode = episodes.return_to_draft(episode_id)
    episodes.update(
        episode_id,
        title=episode.title,
        story_scope=episode.story_scope,
        production_objective=episode.production_objective,
        target_runtime_seconds=episode.target_runtime_seconds,
        continuity_in=episode.continuity_in,
        continuity_out="Landing preparation now begins immediately after orbit insertion.",
        production_constraints=episode.production_constraints,
    )
    episodes.mark_ready(episode_id)

    stale = service.plan(scene.scene_id)
    assert stale is not None
    assert not service.is_upstream_current(stale)
    assert not service.is_production_ready(stale)

    draft = service.return_to_draft(stale.scene_id)
    refreshed = service.update(
        draft.scene_id,
        title=draft.title,
        story_scope=draft.story_scope,
        production_objective=draft.production_objective,
        target_runtime_seconds=draft.target_runtime_seconds,
        setting_requirement=draft.setting_requirement,
        required_events=draft.required_events,
        continuity_in=draft.continuity_in,
        continuity_out=draft.continuity_out,
        scene_constraints=draft.scene_constraints,
    )
    assert service.is_upstream_current(refreshed)
    assert service.is_production_ready(service.mark_ready(refreshed.scene_id))
    context.shutdown()


def test_scene_planner_requires_events_and_normalizes_duplicates(tmp_path: Path) -> None:
    context, _episodes, service, episode_id = _services(tmp_path)
    with pytest.raises(ScenePlanningError, match="required story event"):
        service.create(
            episode_id=episode_id,
            sequence_number=1,
            title="Scene",
            story_scope="Required scope",
            production_objective="Required objective",
            target_runtime_seconds=60,
            setting_requirement="Mauritania bridge",
            required_events=(),
        )

    scene = service.create(
        episode_id=episode_id,
        sequence_number=1,
        title="Scene",
        story_scope="Required scope",
        production_objective="Required objective",
        target_runtime_seconds=60,
        setting_requirement="Mauritania bridge",
        required_events=("Crew sees Xorix", " Crew sees Xorix ", ""),
        scene_constraints=("Preserve scale", " Preserve scale "),
    )
    assert scene.required_events == ("Crew sees Xorix",)
    assert scene.scene_constraints == ("Preserve scale",)
    context.shutdown()
