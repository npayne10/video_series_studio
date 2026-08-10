"""Qt acceptance tests for Phase 19.3.2.1 planning-workspace consolidation."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene, SceneTransition
from vscs.application.story import (
    EpisodePlanningService,
    ScenePlanningService,
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


def _legacy_scene() -> Scene:
    return Scene(
        scene_id="EP-001-SCN-LEGACY",
        episode_id="EP-001",
        sequence_number=99,
        heading="LEGACY STORY WORKSPACE SCENE",
        location_asset_id="CAP-LOC-008",
        summary="Legacy scene data must remain stored but cease to be authoritative planning.",
        participant_asset_ids=("CAP-CHR-001",),
        required_asset_ids=("CAP-LOC-008",),
        time_of_day="day",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=20.0,
        scene_name="Legacy Scene",
    )


def _build_planning(window):
    lifecycle = window.services.require(StoryLifecycleService)
    story = lifecycle.create_story(title="Xorix Short")
    episodes = window.services.require(EpisodePlanningService)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival at Xorix",
        story_scope="Arrival in orbit through landing.",
        production_objective="Establish Xorix and transition into descent.",
        target_runtime_seconds=1200,
        production_constraints=("Keep spacecraft motion physically plausible.",),
    )
    episode = episodes.mark_ready(episode.episode_id)
    scenes = window.services.require(ScenePlanningService)
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania establishes Xorix orbit.",
        production_objective="Establish scale and orbital context.",
        target_runtime_seconds=300,
        setting_requirement="Xorix orbit",
        required_events=("Xorix becomes visible",),
    )
    return story, episode, scene


def test_story_workspace_has_one_authoritative_planning_entry(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    window = context.create_main_window()
    qtbot.addWidget(window)
    window.show()

    workspace = window.story_browser
    assert window.episode_planner_button.text() == "Production Planning…"
    assert window.open_in_planner_button.text() == "Open in Planner"

    for button in (
        workspace.new_button,
        workspace.edit_button,
        workspace.delete_button,
        workspace.plan_button,
        workspace.shot_planner_button,
        workspace.acpp_button,
    ):
        assert button.isHidden()
        assert not button.isEnabled()

    assert workspace.refresh_button.text() == "Refresh Overview"
    context.shutdown()


def test_production_overview_uses_governed_plans_not_legacy_scene_authoring(
    qtbot, tmp_path: Path
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    window = context.create_main_window()
    qtbot.addWidget(window)
    window.show()

    story, episode, scene = _build_planning(window)
    legacy = window.services.require(StoryService)
    legacy.save_scene(_legacy_scene())

    workspace = window.story_browser
    workspace.refresh()
    workspace.story_list.setCurrentRow(0)
    workspace.refresh()

    assert legacy.scene("EP-001-SCN-LEGACY") is not None
    assert workspace.tree.topLevelItemCount() == 1
    episode_item = workspace.tree.topLevelItem(0)
    assert episode_item.text(0) == f"{episode.episode_id} — {episode.title}"
    assert episode_item.text(1) == "Episode Plan"
    assert episode_item.childCount() == 1

    scene_item = episode_item.child(0)
    assert scene_item.text(0) == f"{scene.scene_id} — {scene.title}"
    assert scene_item.text(1) == "Scene Plan"
    assert "Legacy Scene" not in scene_item.text(0)
    assert workspace.dashboard_labels["containers"].text() == "1"
    assert workspace.dashboard_labels["scenes"].text() == "1"
    assert workspace.dashboard_labels["shots"].text() == "0"

    workspace.tree.setCurrentItem(scene_item)
    qtbot.waitUntil(window.open_in_planner_button.isEnabled)
    data = scene_item.data(0, Qt.ItemDataRole.UserRole)
    assert data == ("scene_plan", scene.scene_id, episode.episode_id)
    assert "Edit this plan only through the Scene Planner" in workspace.details.toPlainText()
    assert story.story_id == workspace._selected_story().story_id
    context.shutdown()


def test_production_overview_surfaces_stale_scene_without_restoring_legacy_actions(
    qtbot, tmp_path: Path
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    window = context.create_main_window()
    qtbot.addWidget(window)
    window.show()

    _story, episode, scene = _build_planning(window)
    episodes = window.services.require(EpisodePlanningService)
    scenes = window.services.require(ScenePlanningService)
    scenes.mark_ready(scene.scene_id)
    draft_episode = episodes.return_to_draft(episode.episode_id)
    episodes.update(
        episode.episode_id,
        title=draft_episode.title,
        story_scope=draft_episode.story_scope,
        production_objective=draft_episode.production_objective,
        target_runtime_seconds=draft_episode.target_runtime_seconds,
        continuity_in=draft_episode.continuity_in,
        continuity_out="Descent begins immediately.",
        production_constraints=draft_episode.production_constraints,
    )
    episodes.mark_ready(episode.episode_id)

    workspace = window.story_browser
    workspace.refresh()
    workspace.story_list.setCurrentRow(0)
    workspace.refresh()
    scene_item = workspace.tree.topLevelItem(0).child(0)

    assert scene_item.text(2) == "Ready / Stale"
    assert workspace.new_button.isHidden()
    assert workspace.shot_planner_button.isHidden()
    assert workspace.acpp_button.isHidden()
    context.shutdown()
