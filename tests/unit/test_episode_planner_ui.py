"""Qt tests for the Phase 19.3.1 Episode Planner."""

from __future__ import annotations

from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.story import EpisodePlanningService, StoryLifecycleService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.episode_planner import EpisodePlanEditorDialog, EpisodePlannerDialog


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


def test_episode_editor_is_resizable_scrollable_and_production_focused(
    qtbot, tmp_path: Path
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    story = stories.create_story(title="Xorix")

    dialog = EpisodePlanEditorDialog(story)
    qtbot.addWidget(dialog)
    dialog.resize(640, 480)
    dialog.show()

    assert dialog.minimumWidth() <= 640
    assert dialog.minimumHeight() <= 480
    assert dialog.findChild(type(dialog.scope_edit), "episodeStoryScope") is dialog.scope_edit
    assert (
        dialog.findChild(type(dialog.objective_edit), "episodeProductionObjective")
        is dialog.objective_edit
    )
    assert (
        dialog.findChild(type(dialog.constraints_edit), "episodeProductionConstraints")
        is dialog.constraints_edit
    )
    assert (
        dialog.findChild(type(dialog.runtime_spin), "episodeTargetRuntime") is dialog.runtime_spin
    )
    context.shutdown()


def test_episode_planner_lists_persisted_story_episodes_and_governance(
    qtbot, tmp_path: Path
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    story = stories.create_story(title="Xorix")
    service = EpisodePlanningService(projects, stories)
    plan = service.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival",
        story_scope="Arrival in orbit through landing.",
        production_objective="Establish Xorix and preserve continuity into first contact.",
        target_runtime_seconds=2700,
    )

    dialog = EpisodePlannerDialog(service, story)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "EP-001"
    assert dialog.edit_button.isEnabled()
    assert dialog.ready_button.isEnabled()
    assert not dialog.draft_button.isEnabled()

    service.mark_ready(plan.episode_id)
    dialog.refresh()
    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)
    assert not dialog.edit_button.isEnabled()
    assert dialog.draft_button.isEnabled()
    context.shutdown()


def test_main_story_workspace_exposes_episode_planner_for_selected_story(
    qtbot, tmp_path: Path
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    window = context.create_main_window()
    qtbot.addWidget(window)
    window.show()

    button = window.episode_planner_button
    assert button.objectName() == "episodePlannerButton"
    assert not button.isEnabled()

    lifecycle = window.services.require(StoryLifecycleService)
    lifecycle.create_story(title="Xorix")
    window.story_browser.refresh()
    window.story_browser.story_list.setCurrentRow(0)
    qtbot.waitUntil(button.isEnabled)

    assert button.text() == "Episode Planner…"
    context.shutdown()
