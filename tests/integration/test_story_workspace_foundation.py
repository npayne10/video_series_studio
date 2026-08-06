"""End-to-end coverage for the Phase 18.1 Story Workspace foundation."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryApprovalError,
    StoryApprovalService,
    StoryLifecycleService,
    StoryMetadataError,
    StoryMetadataService,
    StorySourceType,
    StoryStatus,
    StoryStatusService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.help import StoryWorkspaceHelpDialog
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


def _complete_metadata(metadata: StoryMetadataService, story_id: str) -> None:
    metadata.save_metadata(
        story_id,
        synopsis="Humanity discovers a disciplined interstellar civilisation.",
        genres=("Science Fiction",),
        themes=("Discovery", "Responsibility"),
        target_audience="Adult",
        language="English",
        author="S.S. Drake",
        estimated_runtime_minutes=48.0,
        keywords=("first contact", "space exploration"),
        notes="Maintain grounded physical reality.",
    )


def test_complete_story_canon_pipeline_persists(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = context.services.require(StoryLifecycleService)
    metadata = context.services.require(StoryMetadataService)
    statuses = context.services.require(StoryStatusService)
    approvals = context.services.require(StoryApprovalService)

    story = lifecycle.create_story(
        title="Xorix",
        description="A grounded first-contact story.",
        source_type=StorySourceType.DOCX,
        source_path="D:/Stories/Xorix.docx",
    )
    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story structure reviewed",
        changed_by="Neill Payne",
    )
    approvals.approve(
        story.story_id,
        approved_by="Neill Payne",
        notes="Approved as Story Canon",
    )
    approvals.lock(
        story.story_id,
        locked_by="Neill Payne",
        notes="Canon locked for production",
    )

    reloaded_lifecycle = StoryLifecycleService(projects)
    reloaded_metadata = StoryMetadataService(projects, reloaded_lifecycle)
    reloaded_statuses = StoryStatusService(projects, reloaded_lifecycle)
    reloaded_approvals = StoryApprovalService(
        projects,
        reloaded_lifecycle,
        reloaded_metadata,
        reloaded_statuses,
    )
    reloaded = reloaded_lifecycle.story(story.story_id)

    assert reloaded is not None
    assert reloaded.status is StoryStatus.LOCKED
    assert reloaded.source_type is StorySourceType.DOCX
    assert reloaded_metadata.completeness(story.story_id).complete
    assert len(reloaded_statuses.history(story.story_id)) == 1
    assert len(reloaded_approvals.history(story.story_id)) == 2
    context.shutdown()


def test_locked_story_requires_governed_revision_path(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = context.services.require(StoryLifecycleService)
    metadata = context.services.require(StoryMetadataService)
    statuses = context.services.require(StoryStatusService)
    approvals = context.services.require(StoryApprovalService)

    story = lifecycle.create_story(title="Xorix")
    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story reviewed",
    )
    approvals.approve(
        story.story_id,
        approved_by="Neill Payne",
        notes="Approved",
    )
    approvals.lock(
        story.story_id,
        locked_by="Neill Payne",
        notes="Locked",
    )

    with pytest.raises(StoryMetadataError):
        _complete_metadata(metadata, story.story_id)
    with pytest.raises(StoryApprovalError):
        approvals.approve(
            story.story_id,
            approved_by="Neill Payne",
            notes="Duplicate approval",
        )

    approvals.reopen_for_revision(
        story.story_id,
        reopened_by="Neill Payne",
        notes="Canon revision required",
    )
    _complete_metadata(metadata, story.story_id)

    assert lifecycle.story(story.story_id).status is StoryStatus.DRAFT
    context.shutdown()


def test_story_workspace_integrates_help_and_production_browser(
    tmp_path: Path,
    qtbot,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(
        tmp_path / "Demo",
        name="Demo",
    )
    window = context.create_main_window()
    qtbot.addWidget(window)
    workspace = window.story_browser

    assert isinstance(workspace, BrowseableStoryWorkspaceWidget)
    assert hasattr(workspace, "tree")
    assert hasattr(workspace, "shot_plans")
    assert hasattr(workspace, "acpp_button")

    workspace._show_help()
    help_dialog = workspace._story_help_dialog
    qtbot.addWidget(help_dialog)

    assert isinstance(help_dialog, StoryWorkspaceHelpDialog)
    assert help_dialog.section_list.count() == 9
    assert help_dialog.isVisible()
    context.shutdown()


def test_story_archive_restore_retains_previous_status(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = context.services.require(StoryLifecycleService)
    statuses = context.services.require(StoryStatusService)

    story = lifecycle.create_story(
        title="Imported Story",
        source_type=StorySourceType.MARKDOWN,
        source_path="D:/Stories/story.md",
    )
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Analysis complete",
    )
    statuses.archive(story.story_id, reason="Temporarily inactive")
    archived = lifecycle.story(story.story_id)
    statuses.restore(story.story_id, reason="Production resumed")
    restored = lifecycle.story(story.story_id)

    assert archived is not None
    assert archived.status is StoryStatus.ARCHIVED
    assert archived.archived_from_status is StoryStatus.ANALYSED
    assert restored is not None
    assert restored.status is StoryStatus.ANALYSED
    assert len(statuses.history(story.story_id)) == 3
    context.shutdown()
