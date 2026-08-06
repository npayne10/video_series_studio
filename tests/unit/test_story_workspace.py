"""Qt coverage for the Phase 18.1.6 Story Workspace UI."""

from __future__ import annotations

from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.story import StoryStatus
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.story_workspace import (
    StoryEditorDialog,
    StoryWorkspaceWidget,
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


def _workspace(tmp_path: Path, qtbot) -> tuple[object, StoryWorkspaceWidget]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    window = context.create_main_window()
    qtbot.addWidget(window)
    workspace = window.story_browser
    assert isinstance(workspace, StoryWorkspaceWidget)
    return context, workspace


def test_story_editor_returns_normalized_values(qtbot) -> None:
    dialog = StoryEditorDialog()
    qtbot.addWidget(dialog)
    dialog.title_edit.setText("  Xorix  ")
    dialog.genres_edit.setText("Science Fiction, Drama")
    dialog.themes_edit.setText("Discovery, Responsibility")
    dialog.runtime_spin.setValue(48)

    assert dialog.story_values()["title"] == "Xorix"
    assert dialog.metadata_values()["genres"] == (
        "Science Fiction",
        "Drama",
    )
    assert dialog.metadata_values()["estimated_runtime_minutes"] == 48.0


def test_workspace_lists_story_and_displays_readiness(tmp_path: Path, qtbot) -> None:
    context, workspace = _workspace(tmp_path, qtbot)
    story = workspace.lifecycle.create_story(title="Xorix")
    workspace.metadata.save_metadata(
        story.story_id,
        synopsis="A grounded first-contact story.",
        genres=("Science Fiction",),
        themes=("Discovery",),
        target_audience="Adult",
        language="English",
        author="S.S. Drake",
    )

    workspace.refresh()

    assert workspace.story_list.count() == 1
    assert "Xorix" in workspace.story_list.item(0).text()
    assert "100%" in workspace.story_details.text()
    assert workspace.analyse_button.isEnabled()
    assert not workspace.approve_button.isEnabled()
    context.shutdown()  # type: ignore[attr-defined]


def test_workspace_action_state_follows_story_governance(tmp_path: Path, qtbot) -> None:
    context, workspace = _workspace(tmp_path, qtbot)
    story = workspace.lifecycle.create_story(title="Xorix")
    workspace.metadata.save_metadata(
        story.story_id,
        synopsis="A grounded first-contact story.",
        genres=("Science Fiction",),
        themes=("Discovery",),
        target_audience="Adult",
        language="English",
        author="S.S. Drake",
    )
    workspace.statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Analysis complete",
    )

    workspace.refresh()
    assert workspace.approve_button.isEnabled()
    assert not workspace.lock_button.isEnabled()

    workspace.approvals.approve(
        story.story_id,
        approved_by="Neill Payne",
        notes="Approved as Story Canon",
    )
    workspace.refresh()
    assert workspace.lock_button.isEnabled()
    assert workspace.reopen_button.isEnabled()

    workspace.approvals.lock(
        story.story_id,
        locked_by="Neill Payne",
        notes="Canon locked for production",
    )
    workspace.refresh()
    assert workspace.unlock_button.isEnabled()
    assert not workspace.edit_button.isEnabled()
    context.shutdown()  # type: ignore[attr-defined]


def test_workspace_preserves_production_browser_api(tmp_path: Path, qtbot) -> None:
    context, workspace = _workspace(tmp_path, qtbot)

    assert workspace.production_browser is workspace
    assert hasattr(workspace, "tree")
    assert hasattr(workspace, "dashboard_labels")
    assert hasattr(workspace, "shot_plans")
    assert hasattr(workspace, "acpp_button")
    context.shutdown()  # type: ignore[attr-defined]
