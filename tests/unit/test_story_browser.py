"""Tests for the Phase 16.2 Story Browser and SSIE interface."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene, SceneTransition
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.presentation.widgets.story_browser import StoryBrowserWidget


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
        scene_id="SCN-001",
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
    )


def test_story_workspace_replaces_placeholder(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert isinstance(window.content_stack.widget(2), StoryBrowserWidget)
    assert window.story_browser.new_button.isEnabled() is False

    context.shutdown()


def test_story_browser_displays_scene_and_generated_shots(
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

    window.navigation.setCurrentRow(2)
    window.story_browser.refresh()
    assert window.story_browser.tree.topLevelItemCount() == 1
    scene_item = window.story_browser.tree.topLevelItem(0)
    assert "MAURITANIA BRIDGE" in scene_item.text(0)

    stories.plan_scene("SCN-001")
    window.story_browser.refresh()
    scene_item = window.story_browser.tree.topLevelItem(0)
    assert scene_item.childCount() > 0

    shot_item = scene_item.child(0)
    window.story_browser.tree.setCurrentItem(shot_item)
    qtbot.waitUntil(  # type: ignore[attr-defined]
        lambda: shot_item.text(0).split("—", 1)[-1].strip()
        in window.story_browser.details.toPlainText()
    )
    assert "Camera" in window.story_browser.details.toPlainText()
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
    item = window.story_browser.tree.topLevelItem(0)
    window.story_browser.tree.setCurrentItem(item)
    data = item.data(0, Qt.ItemDataRole.UserRole)

    assert data == ("scene", "SCN-001")
    assert "unexplained signal" in window.story_browser.details.toPlainText()

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
        AssetCreate(
            asset_id="LOC-BRIDGE",
            name="Mauritania Bridge",
            category=AssetCategory.LOCATION,
        )
    )
    assets.create(
        AssetCreate(
            asset_id="ENV-XORIX-FOREST",
            name="Xorix Forest",
            category=AssetCategory.ENVIRONMENT,
        )
    )
    assets.create(
        AssetCreate(
            asset_id="PROP-CONSOLE",
            name="Bridge Console",
            category=AssetCategory.PROP,
        )
    )
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    catalog = window.story_browser._location_assets()

    assert [asset.asset_id for asset in catalog] == [
        "LOC-BRIDGE",
        "ENV-XORIX-FOREST",
    ]

    context.shutdown()


def test_story_browser_participant_catalog_contains_characters_only(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate(
            asset_id="CHR-JAMES",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
        )
    )
    assets.create(
        AssetCreate(
            asset_id="CHR-SANDRA",
            name="Sandra Crawford",
            category=AssetCategory.CHARACTER,
        )
    )
    assets.create(
        AssetCreate(
            asset_id="LOC-BRIDGE",
            name="Mauritania Bridge",
            category=AssetCategory.LOCATION,
        )
    )
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    catalog = window.story_browser._participant_assets()

    assert [asset.asset_id for asset in catalog] == ["CHR-JAMES", "CHR-SANDRA"]

    context.shutdown()
