"""Durable mapping from global provider execution identity to production profile."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from vscs.application.production_execution import normalize_execution_profile


@dataclass(frozen=True, slots=True)
class ExecutionProfileAssignment:
    """One immutable profile assignment for a durable execution identity."""

    execution_id: str
    task_id: str
    profile: str
    assigned_at: datetime

    def __post_init__(self) -> None:
        if not self.execution_id.strip():
            raise ValueError("execution_id cannot be blank")
        if not self.task_id.strip():
            raise ValueError("task_id cannot be blank")
        object.__setattr__(self, "profile", normalize_execution_profile(self.profile))


class LocalExecutionProfileStore:
    """Persist profile identity without changing established global queue attempt numbering."""

    SCHEMA_VERSION = 1

    def __init__(self, project_directory: Path) -> None:
        self.path = (
            Path(project_directory).expanduser().resolve(strict=False)
            / ".vscs"
            / "provider_executions"
            / "profiles"
            / "assignments.json"
        )

    def assign(
        self,
        execution_id: str,
        task_id: str,
        profile: str,
        *,
        assigned_at: datetime | None = None,
    ) -> ExecutionProfileAssignment:
        assignment = ExecutionProfileAssignment(
            execution_id=execution_id.strip(),
            task_id=task_id.strip(),
            profile=profile,
            assigned_at=assigned_at or datetime.now(UTC),
        )
        existing = list(self._load())
        current = next(
            (item for item in existing if item.execution_id == assignment.execution_id),
            None,
        )
        if current is not None:
            if current.task_id != assignment.task_id or current.profile != assignment.profile:
                raise ValueError(
                    f"Execution profile assignment conflicts with existing authority: {execution_id}"
                )
            return current
        existing.append(assignment)
        self._write(tuple(existing))
        return assignment

    def profile_for_execution(self, execution_id: str) -> str:
        normalized = execution_id.strip()
        if not normalized:
            raise ValueError("execution_id cannot be blank")
        assignment = next(
            (item for item in self._load() if item.execution_id == normalized),
            None,
        )
        # Executions created before Phase 20.16.2 did not persist profile identity.
        # Treat them as production rather than guessing from incomplete historical data.
        return assignment.profile if assignment is not None else "production"

    def list_for_task(self, task_id: str) -> tuple[ExecutionProfileAssignment, ...]:
        normalized = task_id.strip()
        if not normalized:
            return ()
        return tuple(item for item in self._load() if item.task_id == normalized)

    def _load(self) -> tuple[ExecutionProfileAssignment, ...]:
        if not self.path.is_file():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("Unsupported execution profile assignment schema")
        items = payload.get("assignments", [])
        if not isinstance(items, list):
            raise ValueError("execution profile assignments must be a list")
        return tuple(self._decode(item) for item in items)

    def _write(self, assignments: tuple[ExecutionProfileAssignment, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "assignments": [self._encode(item) for item in assignments],
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=self.path.parent,
            delete=False,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        ) as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        os.replace(temporary, self.path)

    @staticmethod
    def _encode(item: ExecutionProfileAssignment) -> dict[str, object]:
        return {
            "execution_id": item.execution_id,
            "task_id": item.task_id,
            "profile": item.profile,
            "assigned_at": item.assigned_at.isoformat(),
        }

    @staticmethod
    def _decode(payload: object) -> ExecutionProfileAssignment:
        if not isinstance(payload, dict):
            raise ValueError("execution profile assignment must be an object")
        return ExecutionProfileAssignment(
            execution_id=str(payload["execution_id"]),
            task_id=str(payload["task_id"]),
            profile=str(payload["profile"]),
            assigned_at=datetime.fromisoformat(str(payload["assigned_at"])),
        )
