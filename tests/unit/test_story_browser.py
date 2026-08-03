"""Tests for Phase 17.1 Story Browser v2."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene, SceneTransition
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.presentation.widgets.story_browser_v2 import StoryBrowserV2Widget


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
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="James confronts an unexplained signal beyond the ship.",
        participant_asset_ids=("CHR-JAMES",),
        dialogue=("That signal should not be there.",),
        required_asset_ids=("PROP-CONSOLE",),
        time_of_day="night",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=24.0,
        scene_name="Unexplained Signal",
    )


def _scene_item(browser: StoryBrowserV2Widget) -> QTreeWidgetItem:
    production = browser.tree.topLevelItem(0)
    season = production.child(0)
    container = season.child(0)
    act = container.child(0)
    return act.child(0)


def test_story_workspace_uses_story_browser_v2(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert isinstance(window.content_stack.widget(2), StoryBrowserV2Widget)
    assert window.story_browser.new_button.isEnabled() is False

    context.shutdown()


def test_story_browser_displays_production_hierarchy_and_generated_shots(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = context.services.require(StoryService)
    stories.save_scene(_scene())
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.story_browser.refresh()
    production = window.story_browser.tree.topLevelItem(0)
    assert production.text(0) == "Current Production"
    assert production.child(0).text(0) == "Season 1"
    scene_item = _scene_item(window.story_browser)
    assert scene_item.text(0) == "Unexplained Signal"

    stories.plan_scene("EP-001-SCN-001")
    window.story_browser.refresh()
    scene_item = _scene_item(window.story_browser)
    assert scene_item.childCount() > 0

    shot_item = scene_item.child(0)
    window.story_browser.tree.setCurrentItem(shot_item)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: "Camera" in window.story_browser.details.toPlainText()
    )
    assert "Lighting" in window.story_browser.details.toPlainText()

    context.shutdown()


def test_story_browser_scene_selection_exposes_scene_details(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    context.services.require(StoryService).save_scene(_scene())
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    window.story_browser.refresh()
    item = _scene_item(window.story_browser)
    window.story_browser.tree.setCurrentItem(item)
    data = item.data(0, Qt.ItemDataRole.UserRole)
    details = window.story_browser.details.toPlainText()

    assert data[0] == "scene"
    assert data[2] == "EP-001-SCN-001"
    assert "unexplained signal" in details
    assert "PROP-CONSOLE" in details

    context.shutdown()


def test_story_browser_dashboard_and_filters(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    context.services.require(StoryService).save_scene(_scene())
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    browser = window.story_browser
    browser.refresh()

    assert browser.dashboard_labels["containers"].text() == "1"
    assert browser.dashboard_labels["scenes"].text() == "1"
    assert browser.dashboard_labels["ready"].text() == "1"
    assert browser.dashboard_labels["assets"].text() == "3"

    browser.search_edit.setText("unexplained")
    qapp.processEvents()
    assert not _scene_item(browser).isHidden()

    browser.search_edit.setText("does-not-exist")
    qapp.processEvents()
    assert browser.tree.topLevelItem(0).isHidden()

    context.shutdown()


def test_story_browser_location_catalog_filters_asset_categories(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate("LOC-BRIDGE", "Mauritania Bridge", AssetCategory.LOCATION)
    )
    assets.create(
        AssetCreate("ENV-XORIX-FOREST", "Xorix Forest", AssetCategory.ENVIRONMENT)
    )
    assets.create(AssetCreate("PROP-CONSOLE", "Bridge Console", AssetCategory.PROP))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert [asset.asset_id for asset in window.story_browser._location_assets()] == [
        "LOC-BRIDGE",
        "ENV-XORIX-FOREST",
    ]
    context.shutdown()


def test_story_browser_asset_catalogs_separate_characters(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    assets = context.services.require(AssetService)
    assets.create(AssetCreate("CHR-JAMES", "Commander James", AssetCategory.CHARACTER))
    assets.create(AssetCreate("PROP-CONSOLE", "Bridge Console", AssetCategory.PROP))
    assets.create(AssetCreate("SHP-IRON", "Iron Horizon", AssetCategory.SHIP))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert [asset.asset_id for asset in window.story_browser._participant_assets()] == [
        "CHR-JAMES"
    ]
    assert [asset.asset_id for asset in window.story_browser._required_assets()] == [
        "PROP-CONSOLE",
        "SHP-IRON",
    ]
    context.shutdown()
