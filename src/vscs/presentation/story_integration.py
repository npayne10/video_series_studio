"""Install the Story Browser into the existing VSCS main window shell."""

from __future__ import annotations

from typing import Any

from vscs.application.acpp import ACPPEditorService
from vscs.application.assets import AssetService
from vscs.application.shots import ShotPlanningService
from vscs.application.story import StoryService
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)
from vscs.presentation.widgets import story_browser as story_browser_module
from vscs.presentation.widgets.acpp_story_browser import ACPPStoryBrowserWidget
from vscs.presentation.windows.main_window import MainWindow


def install_story_browser() -> None:
    """Install the project-aware Story workspace exactly once."""
    if getattr(MainWindow, "_story_browser_installed", False):
        return

    setattr(  # noqa: B010
        story_browser_module,
        "SceneEditorDialog",
        GuidedFirstSceneEditorDialog,
    )

    original_create_content = MainWindow._create_content_area
    original_update_status = MainWindow._update_status_for_section
    original_update_state = MainWindow._update_project_state
    original_close_project = MainWindow._close_project

    def create_content_area(window: Any) -> None:
        original_create_content(window)
        placeholder = window.content_stack.widget(2)
        window.story_browser = ACPPStoryBrowserWidget(
            window.services.require(StoryService),
            window.services.require(AssetService),
            window.services.require(ShotPlanningService),
            window.services.require(ACPPEditorService),
        )
        window.content_stack.removeWidget(placeholder)
        placeholder.deleteLater()
        window.content_stack.insertWidget(2, window.story_browser)

    def update_status(window: Any, section: str) -> None:
        original_update_status(window, section)
        if section == "Story":
            window.story_browser.refresh()

    def update_state(window: Any) -> None:
        original_update_state(window)
        window.story_browser.refresh()

    def close_project(window: Any) -> None:
        original_close_project(window)
        window.story_browser.refresh()

    setattr(MainWindow, "_create_content_area", create_content_area)  # noqa: B010
    setattr(MainWindow, "_update_status_for_section", update_status)  # noqa: B010
    setattr(MainWindow, "_update_project_state", update_state)  # noqa: B010
    setattr(MainWindow, "_close_project", close_project)  # noqa: B010
    setattr(MainWindow, "_story_browser_installed", True)  # noqa: B010
