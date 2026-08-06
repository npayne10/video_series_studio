"""Tests for the Phase 18.1.2 first-class Story lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.projects import ProjectService
from vscs.application.story import (
    StoryLifecycleError,
    StoryLifecycleService,
    StorySourceType,
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


def _service(tmp_path: Path) -> tuple[object, StoryLifecycleService]:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    return context, StoryLifecycleService(projects)


def test_story_lifecycle_creates_and_persists_stable_identity(tmp_path: Path) -> None:
    context, service = _service(tmp_path)
    story = service.create_story(title="Xorix", description="First-contact novel")

    assert story.story_id == "STORY-001"
    assert story.status is StoryStatus.DRAFT
    assert story.created_at
    assert service.story(story.story_id) == story
    assert service.list_stories() == (story,)
    context.shutdown()  # type: ignore[attr-defined]


def test_imported_story_uses_imported_status_and_can_be_updated(tmp_path: Path) -> None:
    context, service = _service(tmp_path)
    story = service.create_story(
        title="Xorix Manuscript",
        source_type=StorySourceType.DOCX,
        source_path="sources/Xorix.docx",
    )

    assert story.status is StoryStatus.IMPORTED
    updated = service.update_story(
        story.story_id,
        title="Xorix",
        description="Approved working manuscript",
        source_type=StorySourceType.DOCX,
        source_path="sources/Xorix_v2.docx",
    )

    assert updated.story_id == story.story_id
    assert updated.created_at == story.created_at
    assert updated.updated_at >= story.updated_at
    assert updated.source_path.endswith("Xorix_v2.docx")
    context.shutdown()  # type: ignore[attr-defined]


def test_duplicate_has_new_identity_and_editable_draft_state(tmp_path: Path) -> None:
    context, service = _service(tmp_path)
    original = service.create_story(
        title="Xorix",
        source_type=StorySourceType.DOCX,
        source_path="sources/Xorix.docx",
    )

    duplicate = service.duplicate_story(original.story_id, title="Xorix Adaptation")

    assert duplicate.story_id == "STORY-002"
    assert duplicate.story_id != original.story_id
    assert duplicate.status is StoryStatus.DRAFT
    assert duplicate.title == "Xorix Adaptation"
    assert duplicate.archived_at is None
    context.shutdown()  # type: ignore[attr-defined]


def test_archive_restore_and_controlled_delete(tmp_path: Path) -> None:
    context, service = _service(tmp_path)
    story = service.create_story(title="Xorix")

    with pytest.raises(StoryLifecycleError, match="archived"):
        service.delete_story(story.story_id)

    archived = service.archive_story(story.story_id)
    assert archived.status is StoryStatus.ARCHIVED
    assert service.list_stories() == ()
    assert service.list_stories(include_archived=True) == (archived,)

    restored = service.restore_story(story.story_id)
    assert restored.status is StoryStatus.DRAFT
    assert restored.archived_at is None

    service.archive_story(story.story_id)
    assert service.delete_story(story.story_id)
    assert service.story(story.story_id) is None
    context.shutdown()  # type: ignore[attr-defined]


def test_archived_story_must_be_restored_before_editing(tmp_path: Path) -> None:
    context, service = _service(tmp_path)
    story = service.create_story(title="Xorix")
    service.archive_story(story.story_id)

    with pytest.raises(StoryLifecycleError, match="restored"):
        service.update_story(
            story.story_id,
            title="Changed",
            description="",
            source_type=StorySourceType.ORIGINAL,
            source_path="",
        )
    context.shutdown()  # type: ignore[attr-defined]


def test_story_title_is_required(tmp_path: Path) -> None:
    context, service = _service(tmp_path)

    with pytest.raises(ValueError, match="title"):
        service.create_story(title="   ")
    context.shutdown()  # type: ignore[attr-defined]
