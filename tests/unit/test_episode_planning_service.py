"""Tests for the Phase 19.3.1 Episode Planner service."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    EpisodePlan,
    EpisodePlanningError,
    EpisodePlanningService,
    EpisodePlanStatus,
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


def _service(tmp_path: Path) -> tuple[ApplicationContext, EpisodePlanningService, str]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    story = stories.create_story(title="Xorix")
    return context, EpisodePlanningService(projects, stories), story.story_id


def _create(service: EpisodePlanningService, story_id: str, sequence: int = 1) -> EpisodePlan:
    return service.create(
        story_id=story_id,
        sequence_number=sequence,
        title="Arrival at Xorix",
        story_scope="Adapt the arrival in Xorix orbit through landing at the starport.",
        production_objective="Establish Xorix, preserve wonder, and carry the crew into first contact.",
        target_runtime_seconds=2700,
        continuity_in="Mauritania has completed the interstellar transit.",
        continuity_out="The landing party is safely on Xorix and ready to meet the ambassador.",
        production_constraints=(
            "Orbital and atmospheric motion must remain physically plausible.",
            "Do not introduce assets not required by the selected story scope.",
        ),
    )


def test_episode_plan_persists_only_production_level_intent(tmp_path: Path) -> None:
    context, service, story_id = _service(tmp_path)
    plan = _create(service, story_id)

    assert plan.episode_id == "EP-001"
    assert plan.story_id == story_id
    assert plan.status is EpisodePlanStatus.DRAFT
    assert plan.production_ready is False
    assert service.plan("EP-001") == plan
    assert service.list_plans(story_id=story_id) == (plan,)
    context.shutdown()


def test_episode_sequence_and_identity_are_deterministic(tmp_path: Path) -> None:
    context, service, story_id = _service(tmp_path)
    _create(service, story_id, 1)
    second = _create(service, story_id, 2)

    assert second.episode_id == "EP-002"
    assert service.next_sequence_number(story_id) == 3
    with pytest.raises(EpisodePlanningError, match="already exists"):
        _create(service, story_id, 2)
    context.shutdown()


def test_ready_plan_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    context, service, story_id = _service(tmp_path)
    plan = _create(service, story_id)
    ready = service.mark_ready(plan.episode_id)

    assert ready.status is EpisodePlanStatus.READY
    assert ready.production_ready
    with pytest.raises(EpisodePlanningError, match="return to Draft"):
        service.update(
            plan.episode_id,
            title="Changed",
            story_scope=plan.story_scope,
            production_objective=plan.production_objective,
            target_runtime_seconds=plan.target_runtime_seconds,
            continuity_in=plan.continuity_in,
            continuity_out=plan.continuity_out,
            production_constraints=plan.production_constraints,
        )
    with pytest.raises(EpisodePlanningError, match="return to Draft"):
        service.delete(plan.episode_id)

    draft = service.return_to_draft(plan.episode_id)
    assert draft.status is EpisodePlanStatus.DRAFT
    context.shutdown()


def test_episode_planner_rejects_non_production_incomplete_data(tmp_path: Path) -> None:
    context, service, story_id = _service(tmp_path)
    with pytest.raises(EpisodePlanningError, match="Story scope"):
        service.create(
            story_id=story_id,
            sequence_number=1,
            title="Episode One",
            story_scope=" ",
            production_objective="Move the story into production.",
            target_runtime_seconds=2700,
        )
    with pytest.raises(EpisodePlanningError, match="runtime"):
        service.create(
            story_id=story_id,
            sequence_number=1,
            title="Episode One",
            story_scope="Chapter 1",
            production_objective="Move the story into production.",
            target_runtime_seconds=0,
        )
    context.shutdown()


def test_constraints_are_normalized_without_duplicates(tmp_path: Path) -> None:
    context, service, story_id = _service(tmp_path)
    plan = service.create(
        story_id=story_id,
        sequence_number=1,
        title="Episode One",
        story_scope="Chapter 1",
        production_objective="Establish the mission.",
        target_runtime_seconds=2400,
        production_constraints=("Keep scale plausible", " Keep scale plausible ", ""),
    )

    assert plan.production_constraints == ("Keep scale plausible",)
    context.shutdown()
