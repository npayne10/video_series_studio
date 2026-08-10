"""Qt tests for the Phase 19.3.2 Scene Planner."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QPlainTextEdit, QScrollArea

from vscs.application.projects import ProjectService
from vscs.application.story import (
    EpisodePlanningService,
    ScenePlanningService,
    StoryLifecycleService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.episode_planner import EpisodePlannerDialog
from vscs.presentation.widgets.scene_planner import ScenePlanEditorDialog, ScenePlannerDialog


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


def _planning(tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    story = stories.create_story(title="Xorix")
    episodes = EpisodePlanningService(projects, stories)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival",
        story_scope="Arrival in orbit through landing.",
        production_objective="Establish Xorix and first-contact approach.",
        target_runtime_seconds=1200,
        production_constraints=("Keep motion physically plausible.",),
    )
    episode = episodes.mark_ready(episode.episode_id)
    scenes = ScenePlanningService(projects, episodes)
    return context, story, episodes, scenes, episode


def test_scene_editor_is_scrollable_resizable_and_production_focused(qtbot, tmp_path: Path) -> None:
    context, _story, _episodes, _scenes, episode = _planning(tmp_path)
    dialog = ScenePlanEditorDialog(episode, episode.production_constraints)
    qtbot.addWidget(dialog)
    dialog.resize(640, 480)
    dialog.show()

    assert dialog.minimumWidth() <= 640
    assert dialog.minimumHeight() <= 480
    assert dialog.findChild(QScrollArea, "scenePlanScrollArea") is not None
    assert dialog.findChild(QPlainTextEdit, "sceneStoryScope") is dialog.scope_edit
    assert dialog.findChild(QPlainTextEdit, "sceneProductionObjective") is dialog.objective_edit
    assert dialog.findChild(QPlainTextEdit, "sceneRequiredEvents") is dialog.events_edit
    inherited = dialog.findChild(QPlainTextEdit, "sceneInheritedEpisodeConstraints")
    assert inherited is not None
    assert inherited.isReadOnly()
    assert "physically plausible" in inherited.toPlainText()
    context.shutdown()


def test_scene_planner_shows_runtime_budget_and_governance(qtbot, tmp_path: Path) -> None:
    context, _story, _episodes, scenes, episode = _planning(tmp_path)
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania enters Xorix orbit.",
        production_objective="Establish scale and controlled arrival.",
        target_runtime_seconds=300,
        setting_requirement="Xorix orbit",
        required_events=("Xorix becomes visible",),
    )

    dialog = ScenePlannerDialog(scenes, episode)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "EP-001-SCN-001"
    assert "5:00 allocated" in dialog.budget_label.text()
    assert "15:00 remaining" in dialog.budget_label.text()
    assert dialog.edit_button.isEnabled()
    assert dialog.ready_button.isEnabled()
    assert not dialog.draft_button.isEnabled()

    scenes.mark_ready(scene.scene_id)
    dialog.refresh()
    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)
    assert not dialog.edit_button.isEnabled()
    assert dialog.draft_button.isEnabled()
    context.shutdown()


def test_episode_planner_exposes_scene_planner_for_selected_episode(qtbot, tmp_path: Path) -> None:
    context, story, episodes, scenes, episode = _planning(tmp_path)
    dialog = EpisodePlannerDialog(episodes, story, scene_service=scenes)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.scenes_button.objectName() == "scenePlannerButton"
    assert not dialog.scenes_button.isEnabled()
    dialog.table.selectRow(0)
    qtbot.waitUntil(dialog.scenes_button.isEnabled)
    assert dialog.table.item(0, 0).text() == episode.episode_id
    context.shutdown()


def test_scene_planner_surfaces_stale_scene_after_episode_change(qtbot, tmp_path: Path) -> None:
    context, _story, episodes, scenes, episode = _planning(tmp_path)
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania enters orbit.",
        production_objective="Establish Xorix.",
        target_runtime_seconds=300,
        setting_requirement="Xorix orbit",
        required_events=("Xorix becomes visible",),
    )
    scenes.mark_ready(scene.scene_id)
    draft_episode = episodes.return_to_draft(episode.episode_id)
    changed = episodes.update(
        episode.episode_id,
        title=draft_episode.title,
        story_scope=draft_episode.story_scope,
        production_objective=draft_episode.production_objective,
        target_runtime_seconds=draft_episode.target_runtime_seconds,
        continuity_in=draft_episode.continuity_in,
        continuity_out="Descent preparation begins immediately.",
        production_constraints=draft_episode.production_constraints,
    )
    episodes.mark_ready(changed.episode_id)

    current_episode = episodes.plan(episode.episode_id)
    assert current_episode is not None
    dialog = ScenePlannerDialog(scenes, current_episode)
    qtbot.addWidget(dialog)
    dialog.show()

    assert "Stale" in dialog.table.item(0, 3).text()
    stale_scene = scenes.plan(scene.scene_id)
    assert stale_scene is not None
    assert not scenes.is_production_ready(stale_scene)
    context.shutdown()
