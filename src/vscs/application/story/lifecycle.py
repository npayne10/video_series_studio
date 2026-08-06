"""Persistent first-class story lifecycle for Story-Driven Production."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService


class StoryLifecycleError(RuntimeError):
    """Raised when story lifecycle data cannot be processed safely."""


class StoryStatus(StrEnum):
    """Lifecycle states available before analysis and approval phases."""

    DRAFT = "draft"
    IMPORTED = "imported"
    ARCHIVED = "archived"

    @property
    def label(self) -> str:
        """Return a readable UI label."""
        return self.value.title()


class StorySourceType(StrEnum):
    """Supported origins for a story source."""

    ORIGINAL = "original"
    DOCX = "docx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    SCREENPLAY = "screenplay"
    PLAIN_TEXT = "plain_text"
    OTHER = "other"

    @property
    def label(self) -> str:
        """Return a readable UI label."""
        return self.value.replace("_", " ").title()


@dataclass(frozen=True, slots=True)
class StoryRecord:
    """One persistent creative story beneath the active VSCS project."""

    story_id: str
    title: str
    description: str = ""
    source_type: StorySourceType = StorySourceType.ORIGINAL
    source_path: str = ""
    status: StoryStatus = StoryStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""
    archived_at: str | None = None

    @property
    def archived(self) -> bool:
        """Return whether the story is outside the active creative workflow."""
        return self.status is StoryStatus.ARCHIVED


class StoryLifecycleService:
    """Create, edit, duplicate, archive, restore and delete project stories."""

    FILE_NAME = "stories.json"

    def __init__(self, projects: ProjectService) -> None:
        self.projects = projects

    @property
    def story_file(self) -> Path:
        """Return the active project's first-class story registry."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.FILE_NAME

    def list_stories(
        self,
        *,
        include_archived: bool = False,
    ) -> tuple[StoryRecord, ...]:
        """Load stories in stable title and identity order."""
        path = self.story_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            stories = tuple(
                self._from_dict(item) for item in raw.get("stories", [])
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise StoryLifecycleError(
                f"Unable to load stories: {exc}"
            ) from exc
        if not include_archived:
            stories = tuple(story for story in stories if not story.archived)
        return tuple(
            sorted(
                stories,
                key=lambda story: (story.title.casefold(), story.story_id),
            )
        )

    def story(
        self,
        story_id: str,
        *,
        include_archived: bool = True,
    ) -> StoryRecord | None:
        """Return one story by stable identity."""
        return next(
            (
                story
                for story in self.list_stories(
                    include_archived=include_archived
                )
                if story.story_id == story_id
            ),
            None,
        )

    def next_story_id(self) -> str:
        """Return the next available deterministic project-local story identity."""
        existing = {
            story.story_id
            for story in self.list_stories(include_archived=True)
        }
        sequence = 1
        while f"STORY-{sequence:03d}" in existing:
            sequence += 1
        return f"STORY-{sequence:03d}"

    def create_story(
        self,
        *,
        title: str,
        description: str = "",
        source_type: StorySourceType = StorySourceType.ORIGINAL,
        source_path: str = "",
    ) -> StoryRecord:
        """Create a new editable story with a stable project-local identity."""
        normalized_title = self._required(title, "Story title")
        now = self._timestamp()
        story = StoryRecord(
            story_id=self.next_story_id(),
            title=normalized_title,
            description=description.strip(),
            source_type=source_type,
            source_path=source_path.strip(),
            status=(
                StoryStatus.IMPORTED
                if source_type is not StorySourceType.ORIGINAL
                or source_path.strip()
                else StoryStatus.DRAFT
            ),
            created_at=now,
            updated_at=now,
        )
        stories = (*self.list_stories(include_archived=True), story)
        self._write(stories)
        return story

    def update_story(
        self,
        story_id: str,
        *,
        title: str,
        description: str,
        source_type: StorySourceType,
        source_path: str,
    ) -> StoryRecord:
        """Replace editable story details without changing identity or creation time."""
        current = self._require_story(story_id)
        if current.archived:
            raise StoryLifecycleError(
                "Archived stories must be restored before editing"
            )
        updated = replace(
            current,
            title=self._required(title, "Story title"),
            description=description.strip(),
            source_type=source_type,
            source_path=source_path.strip(),
            status=(
                StoryStatus.IMPORTED
                if source_type is not StorySourceType.ORIGINAL
                or source_path.strip()
                else StoryStatus.DRAFT
            ),
            updated_at=self._timestamp(),
        )
        self._replace(updated)
        return updated

    def duplicate_story(
        self,
        story_id: str,
        *,
        title: str | None = None,
    ) -> StoryRecord:
        """Create an editable draft copy without sharing lifecycle identity."""
        source = self._require_story(story_id)
        duplicate_title = title if title is not None else f"{source.title} Copy"
        now = self._timestamp()
        duplicate = replace(
            source,
            story_id=self.next_story_id(),
            title=self._required(duplicate_title, "Story title"),
            status=StoryStatus.DRAFT,
            created_at=now,
            updated_at=now,
            archived_at=None,
        )
        self._write(
            (*self.list_stories(include_archived=True), duplicate)
        )
        return duplicate

    def archive_story(self, story_id: str) -> StoryRecord:
        """Remove a story from active workflow without deleting its history."""
        current = self._require_story(story_id)
        if current.archived:
            return current
        now = self._timestamp()
        archived = replace(
            current,
            status=StoryStatus.ARCHIVED,
            archived_at=now,
            updated_at=now,
        )
        self._replace(archived)
        return archived

    def restore_story(self, story_id: str) -> StoryRecord:
        """Return an archived story to an editable lifecycle state."""
        current = self._require_story(story_id)
        if not current.archived:
            return current
        restored_status = (
            StoryStatus.IMPORTED
            if current.source_type is not StorySourceType.ORIGINAL
            or current.source_path
            else StoryStatus.DRAFT
        )
        restored = replace(
            current,
            status=restored_status,
            archived_at=None,
            updated_at=self._timestamp(),
        )
        self._replace(restored)
        return restored

    def delete_story(self, story_id: str) -> bool:
        """Permanently delete only a story that has already been archived."""
        current = self.story(story_id, include_archived=True)
        if current is None:
            return False
        if not current.archived:
            raise StoryLifecycleError(
                "A story must be archived before permanent deletion"
            )
        remaining = tuple(
            story
            for story in self.list_stories(include_archived=True)
            if story.story_id != story_id
        )
        self._write(remaining)
        return True

    def _require_story(self, story_id: str) -> StoryRecord:
        story = self.story(story_id, include_archived=True)
        if story is None:
            raise StoryLifecycleError(f"Story not found: {story_id}")
        return story

    def _replace(self, replacement: StoryRecord) -> None:
        stories = {
            story.story_id: story
            for story in self.list_stories(include_archived=True)
        }
        stories[replacement.story_id] = replacement
        self._write(tuple(stories.values()))

    def _write(self, stories: tuple[StoryRecord, ...]) -> None:
        path = self.story_file
        path.parent.mkdir(parents=True, exist_ok=True)
        ordered = sorted(
            stories,
            key=lambda story: (story.title.casefold(), story.story_id),
        )
        payload = {
            "schema_version": "1.0",
            "stories": [self._to_dict(story) for story in ordered],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StoryLifecycleError(
                f"Unable to save stories: {exc}"
            ) from exc

    @staticmethod
    def _required(value: str, label: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{label} is required")
        return normalized

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _to_dict(story: StoryRecord) -> dict[str, Any]:
        raw = asdict(story)
        raw["source_type"] = story.source_type.value
        raw["status"] = story.status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> StoryRecord:
        return StoryRecord(
            story_id=str(raw["story_id"]),
            title=str(raw["title"]),
            description=str(raw.get("description", "")),
            source_type=StorySourceType(
                str(raw.get("source_type", StorySourceType.ORIGINAL.value))
            ),
            source_path=str(raw.get("source_path", "")),
            status=StoryStatus(
                str(raw.get("status", StoryStatus.DRAFT.value))
            ),
            created_at=str(raw.get("created_at", "")),
            updated_at=str(raw.get("updated_at", "")),
            archived_at=(
                None
                if raw.get("archived_at") is None
                else str(raw["archived_at"])
            ),
        )
