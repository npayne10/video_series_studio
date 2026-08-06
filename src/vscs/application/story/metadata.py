"""Project-backed metadata for first-class Story records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .lifecycle import StoryLifecycleError, StoryLifecycleService


class StoryMetadataError(RuntimeError):
    """Raised when Story metadata cannot be validated or persisted."""


@dataclass(frozen=True, slots=True)
class StoryMetadata:
    """Creative and editorial metadata attached to one stable Story identity."""

    story_id: str
    synopsis: str = ""
    genres: tuple[str, ...] = ()
    themes: tuple[str, ...] = ()
    target_audience: str = ""
    language: str = "English"
    author: str = ""
    estimated_runtime_minutes: float | None = None
    keywords: tuple[str, ...] = ()
    notes: str = ""
    updated_at: str = ""


@dataclass(frozen=True, slots=True)
class StoryMetadataCompleteness:
    """Explain whether the core Story metadata is ready for later analysis."""

    story_id: str
    completed_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    percentage: int

    @property
    def complete(self) -> bool:
        """Return whether every required metadata field is populated."""
        return not self.missing_fields


class StoryMetadataService:
    """Create, replace, inspect and remove metadata for project Stories."""

    FILE_NAME = "story_metadata.json"
    REQUIRED_FIELDS = (
        "synopsis",
        "genres",
        "themes",
        "target_audience",
        "language",
        "author",
    )

    def __init__(
        self,
        projects: ProjectService,
        stories: StoryLifecycleService,
    ) -> None:
        self.projects = projects
        self.stories = stories

    @property
    def metadata_file(self) -> Path:
        """Return the active project's Story metadata registry path."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.FILE_NAME

    def list_metadata(self) -> tuple[StoryMetadata, ...]:
        """Load all metadata records in stable Story identity order."""
        path = self.metadata_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = tuple(
                self._from_dict(item) for item in raw.get("metadata", [])
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise StoryMetadataError(
                f"Unable to load Story metadata: {exc}"
            ) from exc
        return tuple(sorted(records, key=lambda item: item.story_id))

    def metadata(self, story_id: str) -> StoryMetadata | None:
        """Return metadata for one Story, or ``None`` when not defined."""
        return next(
            (
                item
                for item in self.list_metadata()
                if item.story_id == story_id
            ),
            None,
        )

    def save_metadata(
        self,
        story_id: str,
        *,
        synopsis: str = "",
        genres: tuple[str, ...] = (),
        themes: tuple[str, ...] = (),
        target_audience: str = "",
        language: str = "English",
        author: str = "",
        estimated_runtime_minutes: float | None = None,
        keywords: tuple[str, ...] = (),
        notes: str = "",
    ) -> StoryMetadata:
        """Create or replace normalized metadata for an editable Story."""
        story = self.stories.story(story_id, include_archived=True)
        if story is None:
            raise StoryLifecycleError(f"Story not found: {story_id}")
        if story.archived:
            raise StoryMetadataError(
                "Archived stories must be restored before metadata can be edited"
            )
        if (
            estimated_runtime_minutes is not None
            and estimated_runtime_minutes <= 0
        ):
            raise ValueError(
                "Estimated runtime must be greater than zero when provided"
            )
        metadata = StoryMetadata(
            story_id=story_id,
            synopsis=synopsis.strip(),
            genres=self._normalized_values(genres),
            themes=self._normalized_values(themes),
            target_audience=target_audience.strip(),
            language=language.strip(),
            author=author.strip(),
            estimated_runtime_minutes=estimated_runtime_minutes,
            keywords=self._normalized_values(keywords),
            notes=notes.strip(),
            updated_at=datetime.now(UTC).isoformat(),
        )
        records = {item.story_id: item for item in self.list_metadata()}
        records[story_id] = metadata
        self._write(tuple(records.values()))
        return metadata

    def delete_metadata(self, story_id: str) -> bool:
        """Remove metadata without changing the owning Story lifecycle."""
        records = {item.story_id: item for item in self.list_metadata()}
        removed = records.pop(story_id, None)
        if removed is None:
            return False
        self._write(tuple(records.values()))
        return True

    def completeness(self, story_id: str) -> StoryMetadataCompleteness:
        """Return deterministic readiness details for core Story metadata."""
        metadata = self.metadata(story_id)
        values: dict[str, object] = {
            "synopsis": metadata.synopsis if metadata else "",
            "genres": metadata.genres if metadata else (),
            "themes": metadata.themes if metadata else (),
            "target_audience": metadata.target_audience if metadata else "",
            "language": metadata.language if metadata else "",
            "author": metadata.author if metadata else "",
        }
        completed = tuple(
            field for field in self.REQUIRED_FIELDS if bool(values[field])
        )
        missing = tuple(
            field for field in self.REQUIRED_FIELDS if not bool(values[field])
        )
        percentage = round(100 * len(completed) / len(self.REQUIRED_FIELDS))
        return StoryMetadataCompleteness(
            story_id=story_id,
            completed_fields=completed,
            missing_fields=missing,
            percentage=percentage,
        )

    def _write(self, records: tuple[StoryMetadata, ...]) -> None:
        path = self.metadata_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "metadata": [
                self._to_dict(item)
                for item in sorted(records, key=lambda value: value.story_id)
            ],
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
            raise StoryMetadataError(
                f"Unable to save Story metadata: {exc}"
            ) from exc

    @staticmethod
    def _normalized_values(values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = {
            value.strip()
            for value in values
            if value.strip()
        }
        return tuple(sorted(normalized, key=str.casefold))

    @staticmethod
    def _to_dict(metadata: StoryMetadata) -> dict[str, Any]:
        raw = asdict(metadata)
        raw["genres"] = list(metadata.genres)
        raw["themes"] = list(metadata.themes)
        raw["keywords"] = list(metadata.keywords)
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> StoryMetadata:
        runtime = raw.get("estimated_runtime_minutes")
        return StoryMetadata(
            story_id=str(raw["story_id"]),
            synopsis=str(raw.get("synopsis", "")),
            genres=tuple(str(value) for value in raw.get("genres", [])),
            themes=tuple(str(value) for value in raw.get("themes", [])),
            target_audience=str(raw.get("target_audience", "")),
            language=str(raw.get("language", "English")),
            author=str(raw.get("author", "")),
            estimated_runtime_minutes=(
                None if runtime is None else float(runtime)
            ),
            keywords=tuple(str(value) for value in raw.get("keywords", [])),
            notes=str(raw.get("notes", "")),
            updated_at=str(raw.get("updated_at", "")),
        )
