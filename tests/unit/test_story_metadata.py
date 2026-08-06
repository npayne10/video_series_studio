"""Tests for the Phase 18.1.3 Story metadata foundation."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryLifecycleError,
    StoryLifecycleService,
    StoryMetadataError,
    StoryMetadataService,
    StoryStatus,
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
) -> tuple[object, StoryLifecycleService, StoryMetadataService]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    stories = StoryLifecycleService(projects)
    metadata = StoryMetadataService(projects, stories)
    return context, stories, metadata


def test_metadata_persists_normalized_story_information(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    metadata = metadata_service.save_metadata(
        story.story_id,
        synopsis="  Humanity encounters an engineered world.  ",
        genres=("Science Fiction", "Drama", "Science Fiction"),
        themes=("First Contact", "Responsibility"),
        target_audience="Adult science-fiction readers",
        language="English",
        author="S.S. Drake",
        estimated_runtime_minutes=48.0,
        keywords=("Xorix", "first contact", "Xorix"),
        notes="Reference story for the streaming series.",
    )

    assert metadata.synopsis == "Humanity encounters an engineered world."
    assert metadata.genres == ("Drama", "Science Fiction")
    assert metadata.keywords == ("first contact", "Xorix")
    assert metadata_service.metadata(story.story_id) == metadata
    assert metadata_service.list_metadata() == (metadata,)
    context.shutdown()  # type: ignore[attr-defined]


def test_metadata_can_be_replaced_without_changing_story_identity(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    first = metadata_service.save_metadata(
        story.story_id,
        synopsis="Initial synopsis",
        author="S.S. Drake",
    )

    revised = metadata_service.save_metadata(
        story.story_id,
        synopsis="Revised synopsis",
        genres=("Science Fiction",),
        themes=("Discovery",),
        target_audience="Adult",
        language="English",
        author="S.S. Drake",
    )

    assert revised.story_id == first.story_id
    assert revised.updated_at >= first.updated_at
    assert metadata_service.list_metadata() == (revised,)
    context.shutdown()  # type: ignore[attr-defined]


def test_metadata_completeness_explains_missing_required_fields(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    empty = metadata_service.completeness(story.story_id)
    assert empty.percentage == 0
    assert not empty.complete
    assert empty.missing_fields == metadata_service.REQUIRED_FIELDS

    metadata_service.save_metadata(
        story.story_id,
        synopsis="A grounded first-contact story.",
        genres=("Science Fiction",),
        themes=("Discovery",),
        target_audience="Adult",
        language="English",
        author="S.S. Drake",
    )
    complete = metadata_service.completeness(story.story_id)

    assert complete.percentage == 100
    assert complete.complete
    assert complete.missing_fields == ()
    context.shutdown()  # type: ignore[attr-defined]


def test_metadata_requires_existing_editable_story(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)

    with pytest.raises(StoryLifecycleError, match="Story not found"):
        metadata_service.save_metadata("STORY-999", synopsis="Missing")

    story = stories.create_story(title="Archived Story")
    stories.archive_story(story.story_id)
    with pytest.raises(StoryMetadataError, match="restored"):
        metadata_service.save_metadata(story.story_id, synopsis="Blocked")
    context.shutdown()  # type: ignore[attr-defined]


def test_locked_story_metadata_cannot_be_edited(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Locked Story")
    stories.set_status(story.story_id, StoryStatus.LOCKED)

    with pytest.raises(StoryMetadataError, match="unlocked"):
        metadata_service.save_metadata(story.story_id, synopsis="Blocked")
    context.shutdown()  # type: ignore[attr-defined]


def test_metadata_edit_invalidates_analysed_status(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    stories.set_status(story.story_id, StoryStatus.ANALYSED)

    metadata_service.save_metadata(
        story.story_id,
        synopsis="Revised after analysis",
    )

    current = stories.story(story.story_id)
    assert current is not None
    assert current.status is StoryStatus.DRAFT
    context.shutdown()  # type: ignore[attr-defined]


def test_runtime_must_be_positive_when_provided(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Xorix")

    with pytest.raises(ValueError, match="runtime"):
        metadata_service.save_metadata(
            story.story_id,
            estimated_runtime_minutes=0,
        )
    context.shutdown()  # type: ignore[attr-defined]


def test_metadata_can_be_removed_independently(tmp_path: Path) -> None:
    context, stories, metadata_service = _services(tmp_path)
    story = stories.create_story(title="Xorix")
    metadata_service.save_metadata(story.story_id, synopsis="Temporary")

    assert metadata_service.delete_metadata(story.story_id)
    assert metadata_service.metadata(story.story_id) is None
    assert not metadata_service.delete_metadata(story.story_id)
    assert stories.story(story.story_id) == story
    context.shutdown()  # type: ignore[attr-defined]
