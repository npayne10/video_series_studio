"""Integration coverage for Phase 18.2.9 cache composition."""

from __future__ import annotations

from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.story_analysis import StoryAnalysisCacheService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.browseable_story_workspace import BrowseableStoryWorkspaceWidget


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


def test_story_workspace_receives_persistent_analysis_cache(tmp_path: Path, qtbot) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    window = context.create_main_window()
    qtbot.addWidget(window)

    workspace = window.story_browser

    assert isinstance(workspace, BrowseableStoryWorkspaceWidget)
    cache = context.services.require(StoryAnalysisCacheService)
    assert workspace.analysis_cache is cache
    context.shutdown()
