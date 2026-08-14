"""Functional coverage for the clean-project Story import entry point."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog

from vscs.application.projects import ProjectService
from vscs.application.story import StoryLifecycleService, StorySourceType, StoryStatus
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.browseable_story_workspace import (
    BrowseableStoryWorkspaceWidget,
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


def test_clean_project_exposes_create_and_import_story_actions(
    tmp_path: Path,
    qtbot,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
    window = context.create_main_window()
    qtbot.addWidget(window)
    workspace = window.story_browser

    assert isinstance(workspace, BrowseableStoryWorkspaceWidget)
    assert not workspace.story_new_button.isHidden()
    assert workspace.story_new_button.isEnabled()
    assert not workspace.import_story_button.isHidden()
    assert workspace.import_story_button.isEnabled()
    context.shutdown()


def test_import_story_creates_imported_story_from_selected_file(
    tmp_path: Path,
    qtbot,
    monkeypatch,
) -> None:
    source = tmp_path / "The Silent Relay.txt"
    source.write_text("The Iron Horizon detected a repeating signal.", encoding="utf-8")

    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "VSCS TSR", name="VSCS TSR")
    window = context.create_main_window()
    qtbot.addWidget(window)
    workspace = window.story_browser

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(source), "Plain text files"),
    )

    workspace.import_story_button.click()

    stories = context.services.require(StoryLifecycleService).list_stories()
    assert len(stories) == 1
    assert stories[0].title == "The Silent Relay"
    assert stories[0].source_type is StorySourceType.PLAIN_TEXT
    assert stories[0].source_path == str(source)
    assert stories[0].status is StoryStatus.IMPORTED
    assert workspace.story_list.count() == 1
    context.shutdown()
