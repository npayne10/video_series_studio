"""Integration coverage for the Story Workspace application pipeline."""

from __future__ import annotations

from pathlib import Path

from vscs.application.story import (
    StoryApprovalService,
    StoryLifecycleService,
    StoryMetadataService,
    StoryStatusService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.acpp_story_browser import ACPPStoryBrowserWidget
from vscs.presentation.widgets.story_workspace import StoryWorkspaceWidget


def test_main_window_installs_complete_story_workspace(tmp_path: Path, qtbot) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    window = context.create_main_window()
    qtbot.addWidget(window)

    assert isinstance(window.story_browser, StoryWorkspaceWidget)
    assert isinstance(window.story_browser, ACPPStoryBrowserWidget)
    assert window.story_workspace is window.story_browser
    assert context.services.require(StoryLifecycleService)
    assert context.services.require(StoryMetadataService)
    assert context.services.require(StoryStatusService)
    assert context.services.require(StoryApprovalService)
    assert window.story_browser.production_browser is window.story_browser
    context.shutdown()
