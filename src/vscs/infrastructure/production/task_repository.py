"""Durable JSON persistence adapter for authoritative ProductionTask records."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from vscs.application.production_tasks.models import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAttemptPolicy,
    ProductionTaskAuthority,
    ProductionTaskPriority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.production_tasks.repository import ProductionTaskRepositoryError


class JsonProductionTaskRepository:
    """Persist one immutable ProductionTask JSON document per stable task identity."""

    SCHEMA_VERSION = "1.0"
    _SAFE_ID_CHARACTERS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, task_id: str) -> ProductionTask | None:
        normalized = task_id.strip()
        if not normalized:
            raise ProductionTaskRepositoryError("task_id cannot be blank")
        path = self._path(normalized)
        if not path.exists():
            return None
        return self._read(path)

    def save(self, task: ProductionTask) -> ProductionTask:
        """Atomically create or replace one authoritative task document."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self._path(task.task_id)
            temporary = path.with_suffix(".json.tmp")
            payload = {
                "schema_version": self.SCHEMA_VERSION,
                "task": self._to_payload(task),
            }
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            raise ProductionTaskRepositoryError(
                f"Unable to persist ProductionTask {task.task_id}: {exc}"
            ) from exc
        return task

    def list_for_production(self, production_id: str) -> tuple[ProductionTask, ...]:
        normalized = production_id.strip()
        if not normalized:
            raise ProductionTaskRepositoryError("production_id cannot be blank")
        if not self.root.exists():
            return ()
        tasks = tuple(
            task
            for path in sorted(self.root.glob("*.json"))
            if (task := self._read(path)).production_id == normalized
        )
        return tuple(sorted(tasks, key=lambda item: item.task_id))

    def _read(self, path: Path) -> ProductionTask:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported ProductionTask repository schema: "
                    f"{payload.get('schema_version')!r}"
                )
            task_payload = payload["task"]
            if not isinstance(task_payload, dict):
                raise TypeError("task payload must be an object")
            return self._from_payload(task_payload)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ProductionTaskRepositoryError(
                f"Unable to read ProductionTask document {path}: {exc}"
            ) from exc

    def _path(self, task_id: str) -> Path:
        if any(character not in self._SAFE_ID_CHARACTERS for character in task_id):
            raise ProductionTaskRepositoryError(
                f"ProductionTask identity is not filesystem-safe: {task_id}"
            )
        return self.root / f"{task_id}.json"

    @staticmethod
    def _to_payload(task: ProductionTask) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "production_id": task.production_id,
            "episode_id": task.episode_id,
            "scene_id": task.scene_id,
            "shot_id": task.shot_id,
            "task_type": task.task_type.value,
            "authority": {
                "authority_type": task.authority.authority_type.value,
                "authority_id": task.authority.authority_id,
                "revision": task.authority.revision,
                "fingerprint": task.authority.fingerprint,
                "approved": task.authority.approved,
                "approved_by": task.authority.approved_by,
            },
            "capabilities": [value.value for value in task.capabilities],
            "dependencies": list(task.dependencies),
            "required_inputs": list(task.required_inputs),
            "expected_outputs": list(task.expected_outputs),
            "priority": int(task.priority),
            "state": task.state.value,
            "attempt_policy": {
                "maximum_attempts": task.attempt_policy.maximum_attempts,
                "retry_delay_seconds": task.attempt_policy.retry_delay_seconds,
            },
            "provenance": [list(value) for value in task.provenance],
            "metadata": [list(value) for value in task.metadata],
            "created_at": task.created_at.isoformat(),
        }

    @staticmethod
    def _from_payload(payload: dict[str, Any]) -> ProductionTask:
        authority_payload = payload["authority"]
        attempt_payload = payload["attempt_policy"]
        if not isinstance(authority_payload, dict) or not isinstance(attempt_payload, dict):
            raise TypeError("authority and attempt_policy must be objects")
        return ProductionTask(
            task_id=str(payload["task_id"]),
            production_id=str(payload["production_id"]),
            episode_id=str(payload["episode_id"]),
            scene_id=_optional_string(payload.get("scene_id")),
            shot_id=_optional_string(payload.get("shot_id")),
            task_type=ProductionTaskType(str(payload["task_type"])),
            authority=ProductionTaskAuthority(
                authority_type=ProductionAuthorityType(str(authority_payload["authority_type"])),
                authority_id=str(authority_payload["authority_id"]),
                revision=int(authority_payload["revision"]),
                fingerprint=str(authority_payload["fingerprint"]),
                approved=bool(authority_payload["approved"]),
                approved_by=_optional_string(authority_payload.get("approved_by")),
            ),
            capabilities=tuple(
                ProductionCapability(str(value)) for value in payload["capabilities"]
            ),
            dependencies=tuple(str(value) for value in payload.get("dependencies", [])),
            required_inputs=tuple(str(value) for value in payload.get("required_inputs", [])),
            expected_outputs=tuple(str(value) for value in payload["expected_outputs"]),
            priority=ProductionTaskPriority(int(payload["priority"])),
            state=ProductionTaskState(str(payload["state"])),
            attempt_policy=ProductionTaskAttemptPolicy(
                maximum_attempts=int(attempt_payload["maximum_attempts"]),
                retry_delay_seconds=int(attempt_payload["retry_delay_seconds"]),
            ),
            provenance=tuple(
                (str(value[0]), str(value[1])) for value in payload.get("provenance", [])
            ),
            metadata=tuple((str(value[0]), str(value[1])) for value in payload.get("metadata", [])),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
