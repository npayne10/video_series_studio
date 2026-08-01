"""Stable JSON serialization for production render queues."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from .queue_models import (
    QueueAttempt,
    QueuePriority,
    QueueState,
    RenderQueue,
    RenderQueueEntry,
)
from .queue_validator import RenderQueueValidator


class RenderQueueSerializationError(ValueError):
    """Raised when queue serialization or restoration fails."""


class RenderQueueSerializer:
    """Serialize, restore, and checksum validated render queues."""

    def __init__(self, validator: RenderQueueValidator | None = None) -> None:
        self.validator = validator or RenderQueueValidator()

    def dumps(self, queue: RenderQueue) -> str:
        """Serialize a valid queue to stable JSON."""
        result = self.validator.validate(queue)
        if not result.passed:
            raise RenderQueueSerializationError(
                "; ".join(issue.message for issue in result.issues)
            )
        return json.dumps(
            self.to_dict(queue),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n"

    def loads(self, payload: str) -> RenderQueue:
        """Restore and validate a queue from JSON text."""
        try:
            raw = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise RenderQueueSerializationError(f"Invalid render queue JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise RenderQueueSerializationError("Render queue JSON root must be an object")
        try:
            queue = self.from_dict(raw)
        except (KeyError, TypeError, ValueError) as exc:
            raise RenderQueueSerializationError(
                f"Invalid render queue payload: {exc}"
            ) from exc
        result = self.validator.validate(queue)
        if not result.passed:
            raise RenderQueueSerializationError(
                "; ".join(issue.message for issue in result.issues)
            )
        return queue

    def checksum(self, queue: RenderQueue) -> str:
        """Return a deterministic SHA-256 checksum for a valid queue."""
        encoded = json.dumps(
            self.to_dict(queue),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def to_dict(queue: RenderQueue) -> dict[str, Any]:
        """Convert a queue to JSON-compatible primitives."""
        return {
            "queue_id": queue.queue_id,
            "pipeline_id": queue.pipeline_id,
            "schema_version": queue.schema_version,
            "metadata": dict(queue.metadata),
            "entries": [
                {
                    "entry_id": entry.entry_id,
                    "job_id": entry.job_id,
                    "clip_id": entry.clip_id,
                    "state": entry.state.value,
                    "priority": int(entry.priority),
                    "dependencies": list(entry.dependencies),
                    "maximum_attempts": entry.maximum_attempts,
                    "claimed_by": entry.claimed_by,
                    "available_at": _format_datetime(entry.available_at),
                    "created_at": _format_datetime(entry.created_at),
                    "updated_at": _format_datetime(entry.updated_at),
                    "metadata": [list(item) for item in entry.metadata],
                    "attempts": [
                        {
                            "attempt_number": attempt.attempt_number,
                            "worker_id": attempt.worker_id,
                            "started_at": _format_datetime(attempt.started_at),
                            "completed_at": _format_datetime(attempt.completed_at),
                            "succeeded": attempt.succeeded,
                            "error_message": attempt.error_message,
                        }
                        for attempt in entry.attempts
                    ],
                }
                for entry in queue.entries
            ],
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> RenderQueue:
        """Restore a queue from JSON-compatible primitives."""
        return RenderQueue(
            queue_id=str(raw["queue_id"]),
            pipeline_id=str(raw["pipeline_id"]),
            schema_version=str(raw.get("schema_version", "1.0")),
            metadata={
                str(key): str(value) for key, value in raw.get("metadata", {}).items()
            },
            entries=tuple(
                RenderQueueEntry(
                    entry_id=str(item["entry_id"]),
                    job_id=str(item["job_id"]),
                    clip_id=str(item["clip_id"]),
                    state=QueueState(str(item["state"])),
                    priority=QueuePriority(int(item["priority"])),
                    dependencies=tuple(
                        str(value) for value in item.get("dependencies", [])
                    ),
                    maximum_attempts=int(item.get("maximum_attempts", 3)),
                    attempts=tuple(
                        QueueAttempt(
                            attempt_number=int(attempt["attempt_number"]),
                            worker_id=str(attempt["worker_id"]),
                            started_at=_parse_required_datetime(attempt["started_at"]),
                            completed_at=_parse_optional_datetime(
                                attempt.get("completed_at")
                            ),
                            succeeded=attempt.get("succeeded"),
                            error_message=(
                                None
                                if attempt.get("error_message") is None
                                else str(attempt["error_message"])
                            ),
                        )
                        for attempt in item.get("attempts", [])
                    ),
                    claimed_by=(
                        None if item.get("claimed_by") is None else str(item["claimed_by"])
                    ),
                    available_at=_parse_optional_datetime(item.get("available_at")),
                    created_at=_parse_required_datetime(item["created_at"]),
                    updated_at=_parse_required_datetime(item["updated_at"]),
                    metadata=tuple(
                        (str(pair[0]), str(pair[1]))
                        for pair in item.get("metadata", [])
                    ),
                )
                for item in raw.get("entries", [])
            ),
        )


def _format_datetime(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse_required_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Expected datetime string")
    return datetime.fromisoformat(value)


def _parse_optional_datetime(value: Any) -> datetime | None:
    return None if value is None else _parse_required_datetime(value)
