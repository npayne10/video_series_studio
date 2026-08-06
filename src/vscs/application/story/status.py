"""Validated Story status transitions and persistent transition history."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .lifecycle import (
    StoryLifecycleError,
    StoryLifecycleService,
    StoryRecord,
    StoryStatus,
)


class StoryStatusError(RuntimeError):
    """Raised when a Story status transition is invalid or cannot be saved."""


@dataclass(frozen=True, slots=True)
class StoryStatusTransition:
    """One immutable Story status change recorded for traceability."""

    story_id: str
    previous_status: StoryStatus
    new_status: StoryStatus
    reason: str
    changed_by: str
    changed_at: str


@dataclass(frozen=True, slots=True)
class StoryStatusSnapshot:
    """Current Story status and the ordinary transitions available from it."""

    story_id: str
    status: StoryStatus
    allowed_transitions: tuple[StoryStatus, ...]


class StoryStatusService:
    """Validate Story workflow states and retain deterministic status history."""

    FILE_NAME = "story_status_history.json"
    _RESERVED_TARGETS = frozenset({StoryStatus.APPROVED, StoryStatus.LOCKED})
    _ALLOWED_TRANSITIONS: dict[StoryStatus, tuple[StoryStatus, ...]] = {
        StoryStatus.DRAFT: (StoryStatus.ANALYSED, StoryStatus.ARCHIVED),
        StoryStatus.IMPORTED: (
            StoryStatus.DRAFT,
            StoryStatus.ANALYSED,
            StoryStatus.ARCHIVED,
        ),
        StoryStatus.ANALYSED: (
            StoryStatus.DRAFT,
            StoryStatus.IMPORTED,
            StoryStatus.APPROVED,
            StoryStatus.ARCHIVED,
        ),
        StoryStatus.APPROVED: (
            StoryStatus.ANALYSED,
            StoryStatus.LOCKED,
            StoryStatus.ARCHIVED,
        ),
        StoryStatus.LOCKED: (
            StoryStatus.APPROVED,
            StoryStatus.ARCHIVED,
        ),
        StoryStatus.ARCHIVED: (),
    }

    def __init__(
        self,
        projects: ProjectService,
        stories: StoryLifecycleService,
    ) -> None:
        self.projects = projects
        self.stories = stories

    @property
    def history_file(self) -> Path:
        """Return the active project's Story status-history path."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.FILE_NAME

    def snapshot(self, story_id: str) -> StoryStatusSnapshot:
        """Return current status and ordinary transitions for one Story."""
        story = self._require_story(story_id)
        allowed = tuple(
            status
            for status in self._ALLOWED_TRANSITIONS[story.status]
            if status not in self._RESERVED_TARGETS
        )
        return StoryStatusSnapshot(story.story_id, story.status, allowed)

    def transition(
        self,
        story_id: str,
        new_status: StoryStatus,
        *,
        reason: str,
        changed_by: str = "VSCS User",
    ) -> StoryStatusTransition:
        """Apply one validated non-approval Story status transition."""
        story = self._require_story(story_id)
        if new_status in self._RESERVED_TARGETS:
            raise StoryStatusError(
                f"{new_status.label} status requires the Story approval workflow"
            )
        if new_status is StoryStatus.ARCHIVED:
            return self.archive(
                story_id,
                reason=reason,
                changed_by=changed_by,
            )
        self._validate_transition(story.status, new_status)
        self.stories.set_status(story_id, new_status)
        return self._record(
            story_id,
            story.status,
            new_status,
            reason,
            changed_by,
        )

    def archive(
        self,
        story_id: str,
        *,
        reason: str,
        changed_by: str = "VSCS User",
    ) -> StoryStatusTransition:
        """Archive a Story and record the state from which it was removed."""
        story = self._require_story(story_id)
        self._validate_transition(story.status, StoryStatus.ARCHIVED)
        self.stories.archive_story(story_id)
        return self._record(
            story_id,
            story.status,
            StoryStatus.ARCHIVED,
            reason,
            changed_by,
        )

    def restore(
        self,
        story_id: str,
        *,
        reason: str,
        changed_by: str = "VSCS User",
    ) -> StoryStatusTransition:
        """Restore an archived Story to its pre-archive status."""
        story = self._require_story(story_id)
        if story.status is not StoryStatus.ARCHIVED:
            raise StoryStatusError("Only archived Stories can be restored")
        restored = self.stories.restore_story(story_id)
        return self._record(
            story_id,
            StoryStatus.ARCHIVED,
            restored.status,
            reason,
            changed_by,
        )

    def history(
        self,
        story_id: str | None = None,
    ) -> tuple[StoryStatusTransition, ...]:
        """Load status history in recorded chronological order."""
        path = self.history_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            transitions = tuple(
                self._from_dict(item) for item in raw.get("transitions", [])
            )
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise StoryStatusError(
                f"Unable to load Story status history: {exc}"
            ) from exc
        if story_id is not None:
            transitions = tuple(
                item for item in transitions if item.story_id == story_id
            )
        return transitions

    def _require_story(self, story_id: str) -> StoryRecord:
        try:
            story = self.stories.story(story_id, include_archived=True)
        except StoryLifecycleError as exc:
            raise StoryStatusError(str(exc)) from exc
        if story is None:
            raise StoryStatusError(f"Story not found: {story_id}")
        return story

    def _validate_transition(
        self,
        previous_status: StoryStatus,
        new_status: StoryStatus,
    ) -> None:
        if previous_status is new_status:
            raise StoryStatusError(
                f"Story is already {new_status.label}"
            )
        if new_status not in self._ALLOWED_TRANSITIONS[previous_status]:
            raise StoryStatusError(
                f"Cannot change Story status from {previous_status.label} "
                f"to {new_status.label}"
            )

    def _record(
        self,
        story_id: str,
        previous_status: StoryStatus,
        new_status: StoryStatus,
        reason: str,
        changed_by: str,
    ) -> StoryStatusTransition:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("Story status transition reason is required")
        normalized_actor = changed_by.strip()
        if not normalized_actor:
            raise ValueError("Story status transition actor is required")
        transition = StoryStatusTransition(
            story_id=story_id,
            previous_status=previous_status,
            new_status=new_status,
            reason=normalized_reason,
            changed_by=normalized_actor,
            changed_at=datetime.now(UTC).isoformat(),
        )
        self._write((*self.history(), transition))
        return transition

    def _write(self, transitions: tuple[StoryStatusTransition, ...]) -> None:
        path = self.history_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "transitions": [self._to_dict(item) for item in transitions],
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
            raise StoryStatusError(
                f"Unable to save Story status history: {exc}"
            ) from exc

    @staticmethod
    def _to_dict(transition: StoryStatusTransition) -> dict[str, Any]:
        raw = asdict(transition)
        raw["previous_status"] = transition.previous_status.value
        raw["new_status"] = transition.new_status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> StoryStatusTransition:
        return StoryStatusTransition(
            story_id=str(raw["story_id"]),
            previous_status=StoryStatus(str(raw["previous_status"])),
            new_status=StoryStatus(str(raw["new_status"])),
            reason=str(raw["reason"]),
            changed_by=str(raw["changed_by"]),
            changed_at=str(raw["changed_at"]),
        )
