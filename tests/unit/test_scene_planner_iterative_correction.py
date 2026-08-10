"""Corrective acceptance tests for iterative Scene Planning in Phase 19.3.2.1."""

from __future__ import annotations

from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene
from vscs.application.story import (
    EpisodePlanningService,
    ScenePlanningService,
    StoryLifecycleService,
    StoryService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.iterative_scene_planner import IterativeScenePlannerDialog


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


def _draft_planning(tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = StoryLifecycleService(projects)
    story = lifecycle.create_story(title="Xorix")
    episodes = EpisodePlanningService(projects, lifecycle)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival at Xorix",
        story_scope="Arrival in orbit through landing.",
        production_objective="Establish Xorix and prepare first contact.",
        target_runtime_seconds=2700,
        production_constraints=("Keep motion physically plausible.",),
    )
    legacy_story = StoryService(projects)
    scenes = ScenePlanningService(projects, episodes, legacy_story)
    return context, episodes, scenes, legacy_story, episode


def test_draft_episode_enables_scene_creation_but_not_ready_promotion(qtbot, tmp_path: Path) -> None:
    context, _episodes, scenes, _legacy_story, episode = _draft_planning(tmp_path)
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania enters orbit.",
        production_objective="Establish scale.",
        target_runtime_seconds=300,
        setting_requirement="Xorix orbit",
        required_events=("Xorix becomes visible",),
    )

    dialog = IterativeScenePlannerDialog(scenes, episode)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)

    assert "Draft" in dialog.upstream_label.text()
    assert dialog.new_button.isEnabled()
    assert dialog.edit_button.isEnabled()
    assert dialog.delete_button.isEnabled()
    assert not dialog.ready_button.isEnabled()
    assert scenes.is_upstream_current(scene)
    context.shutdown()


def test_legacy_scenes_are_visible_but_inactive_until_migrated(qtbot, tmp_path: Path) -> None:
    context, _episodes, scenes, legacy_story, episode = _draft_planning(tmp_path)
    legacy_story.save_scene(
        Scene(
            scene_id="EP-001-SCN-007",
            episode_id=episode.episode_id,
            sequence_number=7,
            heading="XORIX ORBIT",
            location_asset_id="CAP-LOC-008",
            summary="Legacy arrival scene preserved from the earlier Story scene creator.",
            participant_asset_ids=("CAP-CHR-001",),
            required_asset_ids=("CAP-LOC-008",),
            estimated_duration_seconds=20.0,
            scene_name="Arrive at Xorix",
        )
    )

    dialog = IterativeScenePlannerDialog(scenes, episode)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 0).text() == "EP-001-SCN-007"
    assert dialog.table.item(0, 3).text() == "Legacy / Inactive"
    assert "migrate" in dialog.table.item(0, 6).text().lower()

    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)
    assert dialog.new_button.isEnabled()
    assert not dialog.edit_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    assert not dialog.ready_button.isEnabled()
    assert not dialog.draft_button.isEnabled()
    context.shutdown()
