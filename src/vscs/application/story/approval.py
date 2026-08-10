"""Governed Story approval, locking, unlocking, and revision history."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService

from .lifecycle import StoryLifecycleService, StoryRecord, StoryStatus
from .metadata import StoryMetadataService
from .status import StoryStatusService


class StoryApprovalError(RuntimeError):
    """Raised when Story approval governance cannot be completed safely."""


class StoryApprovalAction(StrEnum):
    """Governed decisions available after Story analysis."""

    APPROVED = "approved"
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    REOPENED = "reopened"

    @property
    def label(self) -> str:
        """Return a readable action label."""
        return self.value.title()


@dataclass(frozen=True, slots=True)
class StoryApprovalRecord:
    """One immutable Story approval-governance decision."""

    story_id: str
    action: StoryApprovalAction
    previous_status: StoryStatus
    new_status: StoryStatus
    decided_by: str
    notes: str
    decided_at: str


@dataclass(frozen=True, slots=True)
class StoryApprovalSnapshot:
    """Current governance state and operations available for one Story."""

    story_id: str
    status: StoryStatus
    metadata_complete: bool
    can_approve: bool
    can_lock: bool
    can_unlock: bool
    can_reopen: bool


class StoryApprovalService:
    """Approve and protect analysed Story Canon with traceable decisions."""

    FILE_NAME = "story_approval_history.json"

    def __init__(
        self,
        projects: ProjectService,
        stories: StoryLifecycleService,
        metadata: StoryMetadataService,
        statuses: StoryStatusService,
    ) -> None:
        self.projects = projects
        self.stories = stories
        self.metadata = metadata
        self.statuses = statuses

    @property
    def history_file(self) -> Path:
        """Return the active project's Story approval-history path."""
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "story" / self.FILE_NAME

    def snapshot(self, story_id: str) -> StoryApprovalSnapshot:
        """Return approval readiness and available governed operations."""
        story = self._require_story(story_id)
        metadata_complete = self.metadata.completeness(story_id).complete
        return StoryApprovalSnapshot(
            story_id=story.story_id,
            status=story.status,
            metadata_complete=metadata_complete,
            can_approve=(story.status is StoryStatus.ANALYSED and metadata_complete),
            can_lock=story.status is StoryStatus.APPROVED,
            can_unlock=story.status is StoryStatus.LOCKED,
            can_reopen=story.status in {StoryStatus.APPROVED, StoryStatus.LOCKED},
        )

    def approve(
        self,
        story_id: str,
        *,
        approved_by: str,
        notes: str,
    ) -> StoryApprovalRecord:
        """Approve a fully defined analysed Story as creative canon."""
        actor, normalized_notes = self._details(approved_by, notes)
        story = self._require_story(story_id)
        if story.status is not StoryStatus.ANALYSED:
            raise StoryApprovalError("Only an Analysed Story can be approved")
        completeness = self.metadata.completeness(story_id)
        if not completeness.complete:
            missing = ", ".join(completeness.missing_fields)
            raise StoryApprovalError(f"Story metadata is incomplete: {missing}")
        self.stories.set_status(story_id, StoryStatus.APPROVED)
        return self._record(
            story_id,
            StoryApprovalAction.APPROVED,
            story.status,
            StoryStatus.APPROVED,
            actor,
            normalized_notes,
        )

    def lock(
        self,
        story_id: str,
        *,
        locked_by: str,
        notes: str,
    ) -> StoryApprovalRecord:
        """Lock approved Story Canon against ordinary editing."""
        actor, normalized_notes = self._details(locked_by, notes)
        story = self._require_story(story_id)
        if story.status is not StoryStatus.APPROVED:
            raise StoryApprovalError("Only an Approved Story can be locked")
        self.stories.set_status(story_id, StoryStatus.LOCKED)
        return self._record(
            story_id,
            StoryApprovalAction.LOCKED,
            StoryStatus.APPROVED,
            StoryStatus.LOCKED,
            actor,
            normalized_notes,
        )

    def unlock(
        self,
        story_id: str,
        *,
        unlocked_by: str,
        notes: str,
    ) -> StoryApprovalRecord:
        """Unlock Story Canon while retaining its approved state."""
        actor, normalized_notes = self._details(unlocked_by, notes)
        story = self._require_story(story_id)
        if story.status is not StoryStatus.LOCKED:
            raise StoryApprovalError("Only a Locked Story can be unlocked")
        self.stories.set_status(story_id, StoryStatus.APPROVED)
        return self._record(
            story_id,
            StoryApprovalAction.UNLOCKED,
            StoryStatus.LOCKED,
            StoryStatus.APPROVED,
            actor,
            normalized_notes,
        )

    def reopen_for_revision(
        self,
        story_id: str,
        *,
        reopened_by: str,
        notes: str,
    ) -> StoryApprovalRecord:
        """Return approved or locked Story Canon to analysed revision state."""
        actor, normalized_notes = self._details(reopened_by, notes)
        story = self._require_story(story_id)
        if story.status not in {StoryStatus.APPROVED, StoryStatus.LOCKED}:
            raise StoryApprovalError(
                "Only an Approved or Locked Story can be reopened for revision"
            )
        self.stories.set_status(story_id, StoryStatus.ANALYSED)
        return self._record(
            story_id,
            StoryApprovalAction.REOPENED,
            story.status,
            StoryStatus.ANALYSED,
            actor,
            normalized_notes,
        )

    def latest(self, story_id: str) -> StoryApprovalRecord | None:
        """Return the latest governance decision for one Story."""
        records = self.history(story_id)
        return records[-1] if records else None

    def history(
        self,
        story_id: str | None = None,
    ) -> tuple[StoryApprovalRecord, ...]:
        """Load approval history in deterministic recorded order."""
        path = self.history_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            records = tuple(self._from_dict(item) for item in raw.get("records", []))
        except (
            OSError,
            json.JSONDecodeError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise StoryApprovalError(f"Unable to load Story approval history: {exc}") from exc
        if story_id is not None:
            records = tuple(record for record in records if record.story_id == story_id)
        return records

    def _require_story(self, story_id: str) -> StoryRecord:
        story = self.stories.story(story_id, include_archived=True)
        if story is None:
            raise StoryApprovalError(f"Story not found: {story_id}")
        if story.status is StoryStatus.ARCHIVED:
            raise StoryApprovalError("Archived Stories must be restored before approval governance")
        return story

    @staticmethod
    def _details(actor: str, notes: str) -> tuple[str, str]:
        normalized_actor = actor.strip()
        if not normalized_actor:
            raise ValueError("Story approval decision maker is required")
        normalized_notes = notes.strip()
        if not normalized_notes:
            raise ValueError("Story approval notes are required")
        return normalized_actor, normalized_notes

    def _record(
        self,
        story_id: str,
        action: StoryApprovalAction,
        previous_status: StoryStatus,
        new_status: StoryStatus,
        decided_by: str,
        notes: str,
    ) -> StoryApprovalRecord:
        record = StoryApprovalRecord(
            story_id=story_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            decided_by=decided_by,
            notes=notes,
            decided_at=datetime.now(UTC).isoformat(),
        )
        self._write((*self.history(), record))
        return record

    def _write(self, records: tuple[StoryApprovalRecord, ...]) -> None:
        path = self.history_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "records": [self._to_dict(record) for record in records],
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
            raise StoryApprovalError(f"Unable to save Story approval history: {exc}") from exc

    @staticmethod
    def _to_dict(record: StoryApprovalRecord) -> dict[str, Any]:
        raw = asdict(record)
        raw["action"] = record.action.value
        raw["previous_status"] = record.previous_status.value
        raw["new_status"] = record.new_status.value
        return raw

    @staticmethod
    def _from_dict(raw: dict[str, Any]) -> StoryApprovalRecord:
        return StoryApprovalRecord(
            story_id=str(raw["story_id"]),
            action=StoryApprovalAction(str(raw["action"])),
            previous_status=StoryStatus(str(raw["previous_status"])),
            new_status=StoryStatus(str(raw["new_status"])),
            decided_by=str(raw["decided_by"]),
            notes=str(raw["notes"]),
            decided_at=str(raw["decided_at"]),
        )
