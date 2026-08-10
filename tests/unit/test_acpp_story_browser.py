"""Tests for Story Browser integration of the Phase 17.3 ACPP Editor."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot, ShotPlanningService
from vscs.application.ssie import Scene
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.acpp_story_browser import ACPPStoryBrowserWidget


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


def test_story_browser_enables_acpp_only_for_production_shot(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    scene = Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The crew studies the signal.",
    )
    context.services.require(StoryService).save_scene(scene)
    shot = ProductionShot(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Master",
        description="Master view of the bridge.",
    )
    context.services.require(ShotPlanningService).save_shot(shot)
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.story_browser.refresh()

    assert isinstance(window.story_browser, ACPPStoryBrowserWidget)
    assert not window.story_browser.acpp_button.isEnabled()
    production_shot = next(
        item
        for item in window.story_browser._walk_items()
        if (data := item.data(0, Qt.ItemDataRole.UserRole))
        and str(data[0]) == window.story_browser.SHOT_KIND
    )
    window.story_browser.tree.setCurrentItem(production_shot)
    qapp.processEvents()
    assert window.story_browser.acpp_button.isEnabled()
    context.shutdown()
