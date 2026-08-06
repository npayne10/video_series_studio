"""Tests for Phase 18.1.4 Story status workflow."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryLifecycleError,
    StoryLifecycleService,
    StoryStatus,
    StoryStatusError,
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
) -> tuple[object, StoryLifecycleService, StoryStatusService]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    statuses = StoryStatusService(projects, stories)
    return context, stories, statuses


def test_snapshot_exposes_only_ordinary_status_transitions(tmp_path: Path) -> None:
    context, stories, statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    snapshot = statuses.snapshot(story.story_id)

    assert snapshot.status is StoryStatus.DRAFT
    assert snapshot.allowed_transitions == (
        StoryStatus.ANALYSED,
        StoryStatus.ARCHIVED,
    )
    context.shutdown()  # type: ignore[attr-defined]


def test_status_transition_updates_story_and_persists_history(tmp_path: Path) -> None:
    context, stories, statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    transition = statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Initial structured analysis completed",
        changed_by="Neill Payne",
    )

    current = stories.story(story.story_id)
    assert current is not None
    assert transition.previous_status is StoryStatus.DRAFT
    assert transition.new_status is StoryStatus.ANALYSED
    assert transition.changed_by == "Neill Payne"
    assert current.status is StoryStatus.ANALYSED
    assert statuses.history(story.story_id) == (transition,)
    context.shutdown()  # type: ignore[attr-defined]


def test_approval_and_lock_statuses_require_approval_workflow(tmp_path: Path) -> None:
    context, stories, statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Analysis completed",
    )

    with pytest.raises(StoryStatusError, match="approval workflow"):
        statuses.transition(
            story.story_id,
            StoryStatus.APPROVED,
            reason="Attempted direct approval",
        )

    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.ANALYSED
    context.shutdown()  # type: ignore[attr-defined]


def test_invalid_details_do_not_mutate_story_status(tmp_path: Path) -> None:
    context, stories, statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    with pytest.raises(ValueError, match="reason"):
        statuses.transition(
            story.story_id,
            StoryStatus.ANALYSED,
            reason="   ",
        )

    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.DRAFT
    assert statuses.history(story.story_id) == ()
    context.shutdown()  # type: ignore[attr-defined]


def test_archive_and_restore_preserve_pre_archive_status(tmp_path: Path) -> None:
    context, stories, statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Analysis completed",
    )

    archived = statuses.archive(
        story.story_id,
        reason="Temporarily removed from active development",
    )
    restored = statuses.restore(
        story.story_id,
        reason="Returned to active development",
    )

    assert archived.new_status is StoryStatus.ARCHIVED
    assert restored.new_status is StoryStatus.ANALYSED
    restored_story = stories.story(story.story_id)
    assert restored_story is not None
    assert restored_story.status is StoryStatus.ANALYSED
    assert restored_story.archived_from_status is None
    assert len(statuses.history(story.story_id)) == 3
    context.shutdown()  # type: ignore[attr-defined]


def test_editing_analysed_story_returns_it_to_editable_status(tmp_path: Path) -> None:
    context, stories, statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    statuses.transition(
        story.story_id,
        StoryStatus.ANALYSED,
        reason="Analysis completed",
    )

    updated = stories.update_story(
        story.story_id,
        title="Xorix Revised",
        description="Story changed after analysis",
        source_type=story.source_type,
        source_path=story.source_path,
    )

    assert updated.status is StoryStatus.DRAFT
    context.shutdown()  # type: ignore[attr-defined]


def test_locked_story_cannot_be_edited_directly(tmp_path: Path) -> None:
    context, stories, _statuses = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    stories.set_status(story.story_id, StoryStatus.LOCKED)

    with pytest.raises(StoryLifecycleError, match="approval workflow"):
        stories.update_story(
            story.story_id,
            title="Changed",
            description="",
            source_type=story.source_type,
            source_path=story.source_path,
        )
    context.shutdown()  # type: ignore[attr-defined]
