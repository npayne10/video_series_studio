"""Qt acceptance tests for the Phase 19.3.3 governed Shot Planner."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QPlainTextEdit, QScrollArea

from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.story import (
    EpisodePlanningService,
    GovernedShotPlanningService,
    ScenePlanningService,
    StoryLifecycleService,
    StoryService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.governed_shot_planner import (
    GovernedShotPlannerDialog,
    ShotPlanEditorDialog,
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


def _planning(tmp_path: Path):
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
        target_runtime_seconds=60,
        setting_requirement="Xorix orbit",
        required_events=("Xorix fills the forward view",),
        scene_constraints=("Keep motion physically plausible.",),
    )
    scene = scenes.mark_ready(scene.scene_id)
    legacy = ShotPlanningService(projects)
    shots = GovernedShotPlanningService(projects, scenes, legacy)
    return context, shots, legacy, scene


def test_shot_editor_is_lean_scrollable_and_defers_specialist_decisions(
    qtbot,
    tmp_path: Path,
) -> None:
    context, _shots, _legacy, scene = _planning(tmp_path)
    dialog = ShotPlanEditorDialog(scene, scene.scene_constraints)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.findChild(QScrollArea, "shotPlanScrollArea") is not None
    inherited = dialog.findChild(QPlainTextEdit, "shotInheritedSceneConstraints")
    assert inherited is not None
    assert inherited.isReadOnly()
    assert "physically plausible" in inherited.toPlainText()
    assert dialog.findChildren(QComboBox) == []
    context.shutdown()


def test_governed_shot_planner_shows_budget_governance_and_legacy_rows(
    qtbot,
    tmp_path: Path,
) -> None:
    context, shots, legacy, scene = _planning(tmp_path)
    shot = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Reveal Xorix",
        narrative_purpose="Reveal planetary scale.",
        production_objective="Orient the audience.",
        target_runtime_seconds=5,
        required_action="Mauritania crosses frame.",
    )
    legacy.save_shot(
        ProductionShot(
            shot_id=f"{scene.scene_id}-SHT-007",
            scene_id=scene.scene_id,
            sequence_number=7,
            title="Legacy reveal",
            description="Legacy Phase 17 shot.",
            estimated_duration_seconds=5.0,
        )
    )

    dialog = GovernedShotPlannerDialog(shots, scene)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.table.rowCount() == 2
    assert "0:05 allocated" in dialog.budget_label.text()
    assert dialog.table.item(1, 3).text() == "Legacy / Inactive"

    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)
    assert dialog.edit_button.isEnabled()
    assert dialog.ready_button.isEnabled()

    shots.mark_ready(shot.shot_id)
    dialog.refresh()
    dialog.table.selectRow(0)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 0)
    assert not dialog.edit_button.isEnabled()
    assert dialog.draft_button.isEnabled()

    dialog.table.selectRow(1)
    qtbot.waitUntil(lambda: dialog.table.currentRow() == 1)
    assert not dialog.edit_button.isEnabled()
    assert not dialog.delete_button.isEnabled()
    assert not dialog.ready_button.isEnabled()
    context.shutdown()
