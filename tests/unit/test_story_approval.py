"""Tests for Phase 18.1.5 Story approval governance."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryApprovalAction,
    StoryApprovalError,
    StoryApprovalService,
    StoryLifecycleService,
    StoryMetadataService,
    StoryStatus,
    StoryStatusService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


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


def _services(
    tmp_path: Path,
) -> tuple[
    object,
    StoryLifecycleService,
    StoryMetadataService,
    StoryStatusService,
    StoryApprovalService,
]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    metadata = StoryMetadataService(projects, stories)
    statuses = StoryStatusService(projects, stories)
    approvals = StoryApprovalService(projects, stories, metadata, statuses)
    return context, stories, metadata, statuses, approvals


def _complete_metadata(
    metadata: StoryMetadataService,
    story_id: str,
) -> None:
    metadata.save_metadata(
        story_id,
        synopsis="Humanity encounters an engineered world.",
        genres=("Science Fiction",),
        themes=("Discovery",),
        target_audience="Adult",
        language="English",
        author="S.S. Drake",
    )


def test_analysed_complete_story_can_be_approved(tmp_path: Path) -> None:
    context, stories, metadata, statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story analysis completed",
    )

    record = approvals.approve(
        story.story_id,
        approved_by="Neill Payne",
        notes="Approved as the creative source for production.",
    )

    assert record.action is StoryApprovalAction.APPROVED
    assert record.previous_status is StoryStatus.ANALYSED
    assert record.new_status is StoryStatus.APPROVED
    approved = stories.story(story.story_id)
    assert approved is not None
    assert approved.status is StoryStatus.APPROVED
    assert approvals.latest(story.story_id) == record
    context.shutdown()  # type: ignore[attr-defined]


def test_approval_requires_complete_metadata(tmp_path: Path) -> None:
    context, stories, _metadata, statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story analysis completed",
    )

    with pytest.raises(StoryApprovalError, match="metadata is incomplete"):
        approvals.approve(
            story.story_id,
            approved_by="Neill Payne",
            notes="Attempted approval.",
        )

    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.ANALYSED
    assert approvals.history(story.story_id) == ()
    context.shutdown()  # type: ignore[attr-defined]


def test_approval_requires_analysed_status(tmp_path: Path) -> None:
    context, stories, metadata, _statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    _complete_metadata(metadata, story.story_id)

    with pytest.raises(StoryApprovalError, match="Analysed"):
        approvals.approve(
            story.story_id,
            approved_by="Neill Payne",
            notes="Attempted approval.",
        )
    context.shutdown()  # type: ignore[attr-defined]


def test_approved_story_can_be_locked_and_unlocked(tmp_path: Path) -> None:
    context, stories, metadata, statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story analysis completed",
    )
    approvals.approve(
        story.story_id,
        approved_by="Neill Payne",
        notes="Approved for production.",
    )

    locked = approvals.lock(
        story.story_id,
        locked_by="Neill Payne",
        notes="Lock the approved canon baseline.",
    )
    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.LOCKED
    assert locked.action is StoryApprovalAction.LOCKED

    unlocked = approvals.unlock(
        story.story_id,
        unlocked_by="Neill Payne",
        notes="Allow controlled review without reopening revision.",
    )
    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.APPROVED
    assert unlocked.action is StoryApprovalAction.UNLOCKED
    assert len(approvals.history(story.story_id)) == 3
    context.shutdown()  # type: ignore[attr-defined]


def test_approved_or_locked_story_can_be_reopened_for_revision(
    tmp_path: Path,
) -> None:
    context, stories, metadata, statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story analysis completed",
    )
    approvals.approve(
        story.story_id,
        approved_by="Neill Payne",
        notes="Approved for production.",
    )
    approvals.lock(
        story.story_id,
        locked_by="Neill Payne",
        notes="Lock approved canon.",
    )

    reopened = approvals.reopen_for_revision(
        story.story_id,
        reopened_by="Neill Payne",
        notes="Revision required after continuity review.",
    )

    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.ANALYSED
    assert reopened.previous_status is StoryStatus.LOCKED
    assert reopened.action is StoryApprovalAction.REOPENED
    context.shutdown()  # type: ignore[attr-defined]


def test_invalid_approval_details_do_not_change_status(tmp_path: Path) -> None:
    context, stories, metadata, statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story analysis completed",
    )

    with pytest.raises(ValueError, match="decision maker"):
        approvals.approve(
            story.story_id,
            approved_by="   ",
            notes="Approved.",
        )

    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.ANALYSED
    assert approvals.history(story.story_id) == ()
    context.shutdown()  # type: ignore[attr-defined]


def test_snapshot_reports_governed_actions(tmp_path: Path) -> None:
    context, stories, metadata, statuses, approvals = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    draft = approvals.snapshot(story.story_id)
    assert not draft.can_approve
    assert not draft.metadata_complete

    _complete_metadata(metadata, story.story_id)
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Story analysis completed",
    )
    analysed = approvals.snapshot(story.story_id)

    assert analysed.metadata_complete
    assert analysed.can_approve
    assert not analysed.can_lock
    context.shutdown()  # type: ignore[attr-defined]
