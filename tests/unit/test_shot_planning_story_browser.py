"""Tests for Shot Planner integration with Story Browser v2."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.ssie import Scene, SceneTransition
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.shot_planning_story_browser import (
    ShotPlanningStoryBrowserWidget,
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


def _scene() -> Scene:
    return Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        scene_name="Signal on the Bridge",
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="James and the crew investigate an impossible signal.",
        participant_asset_ids=("CHR-JAMES",),
        required_asset_ids=("PROP-CONSOLE",),
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=30.0,
    )


def _find_kind(
    browser: ShotPlanningStoryBrowserWidget,
    kind: str,
):
    for item in browser._walk_items():
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and str(data[0]) == kind:
            return item
    return None


def _legacy_shot_browser(context, qtbot: object) -> ShotPlanningStoryBrowserWidget:
    browser = ShotPlanningStoryBrowserWidget(
        context.services.require(StoryService),
        context.services.require(AssetService),
        context.services.require(ShotPlanningService),
    )
    qtbot.addWidget(browser)  # type: ignore[attr-defined]
    browser.refresh()
    return browser


def test_story_browser_exposes_shot_planner_for_scene(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    context.services.require(StoryService).save_scene(_scene())
    browser = _legacy_shot_browser(context, qtbot)

    scene_item = _find_kind(browser, "scene")
    assert scene_item is not None
    browser.tree.setCurrentItem(scene_item)
    qapp.processEvents()
    assert browser.shot_planner_button.isEnabled()
    context.shutdown()


def test_story_browser_displays_persistent_production_shot(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    context.services.require(StoryService).save_scene(_scene())
    browser = _legacy_shot_browser(context, qtbot)
    browser.shot_plans.save_shot(
        ProductionShot(
            shot_id="EP-001-SCN-001-SHT-001",
            scene_id="EP-001-SCN-001",
            sequence_number=1,
            title="Bridge establishing",
            description="Wide establishing shot of the active bridge.",
            estimated_duration_seconds=7.0,
        )
    )
    browser.refresh()

    shot_item = _find_kind(browser, browser.SHOT_KIND)
    assert shot_item is not None
    assert "Bridge establishing" in shot_item.text(0)
    browser.tree.setCurrentItem(shot_item)
    qapp.processEvents()
    details = browser.details.toPlainText()
    assert "Bridge establishing" in details
    assert "Camera" in details
    assert "Storyboard" in details
    context.shutdown()
