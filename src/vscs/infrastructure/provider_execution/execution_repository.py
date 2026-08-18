"""Durable JSON persistence for provider execution jobs."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from vscs.application.provider_execution.execution_records import (
    DurableExecutionEvent,
    DurableExecutionJob,
)
from vscs.application.provider_execution.execution_repository import (
    DurableExecutionJobRepositoryError,
)
from vscs.application.provider_execution.models import ProviderExecutionState


class JsonDurableExecutionJobRepository:
    """Persist one schema-versioned JSON document per VSCS execution identity."""

    SCHEMA_VERSION = "1.0"
    _SAFE_ID_CHARACTERS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, execution_id: str) -> DurableExecutionJob | None:
        normalized = self._require_query(execution_id, "execution_id")
        path = self._path(normalized)
        if not path.exists():
            return None
        return self._read(path)

    def save(self, job: DurableExecutionJob) -> DurableExecutionJob:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "execution_job": self._to_payload(job),
        }
        self._write_atomic(self._path(job.execution_id), payload)
        return job

    def list_for_task(self, task_id: str) -> tuple[DurableExecutionJob, ...]:
        normalized = self._require_query(task_id, "task_id")
        return self._matching(lambda job: job.task_id == normalized)

    def list_for_queue_entry(self, queue_id: str, entry_id: str) -> tuple[DurableExecutionJob, ...]:
        queue = self._require_query(queue_id, "queue_id")
        entry = self._require_query(entry_id, "entry_id")
        return self._matching(lambda job: job.queue_id == queue and job.entry_id == entry)

    def list_for_provider(self, provider_id: str) -> tuple[DurableExecutionJob, ...]:
        normalized = self._require_query(provider_id, "provider_id")
        return self._matching(lambda job: job.provider_id == normalized)

    def list_active(self) -> tuple[DurableExecutionJob, ...]:
        return self._matching(lambda job: not job.terminal)

    def _matching(
        self,
        predicate: Callable[[DurableExecutionJob], bool],
    ) -> tuple[DurableExecutionJob, ...]:
        if not self.root.exists():
            return ()
        jobs = tuple(self._read(path) for path in sorted(self.root.glob("*.json")))
        matching = tuple(job for job in jobs if predicate(job))
        return tuple(
            sorted(
                matching,
                key=lambda job: (job.task_id, job.attempt_number, job.execution_id),
            )
        )

    def _read(self, path: Path) -> DurableExecutionJob:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("execution repository payload must be an object")
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported execution repository schema: {payload.get('schema_version')!r}"
                )
            raw = payload["execution_job"]
            if not isinstance(raw, dict):
                raise TypeError("execution_job payload must be an object")
            return self._from_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise DurableExecutionJobRepositoryError(
                f"Unable to read durable execution job {path}: {exc}"
            ) from exc

    def _path(self, execution_id: str) -> Path:
        normalized = execution_id.strip()
        if not normalized or any(
            character not in self._SAFE_ID_CHARACTERS for character in normalized
        ):
            raise DurableExecutionJobRepositoryError(
                f"Execution identity is not filesystem-safe: {execution_id!r}"
            )
        return self.root / f"{normalized}.json"

    def _write_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise DurableExecutionJobRepositoryError(
                f"Unable to persist durable execution job {path}: {exc}"
            ) from exc

    @staticmethod
    def _to_payload(job: DurableExecutionJob) -> dict[str, Any]:
        return {
            "execution_id": job.execution_id,
            "production_id": job.production_id,
            "task_id": job.task_id,
            "queue_id": job.queue_id,
            "entry_id": job.entry_id,
            "resource_id": job.resource_id,
            "worker_id": job.worker_id,
            "lease_id": job.lease_id,
            "attempt_number": job.attempt_number,
            "authority_fingerprint": job.authority_fingerprint,
            "provider_id": job.provider_id,
            "provider_job_id": job.provider_job_id,
            "render_request_id": job.render_request_id,
            "workflow_id": job.workflow_id,
            "state": job.state.value,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "submitted_at": job.submitted_at.isoformat() if job.submitted_at is not None else None,
            "progress": job.progress,
            "failure_reason": job.failure_reason,
            "events": [
                {
                    "state": event.state.value,
                    "observed_at": event.observed_at.isoformat(),
                    "progress": event.progress,
                    "provider_job_id": event.provider_job_id,
                    "failure_reason": event.failure_reason,
                }
                for event in job.events
            ],
        }

    @staticmethod
    def _from_payload(raw: dict[str, Any]) -> DurableExecutionJob:
        events_raw = raw.get("events", [])
        if not isinstance(events_raw, list):
            raise TypeError("events must be an array")
        return DurableExecutionJob(
            execution_id=str(raw["execution_id"]),
            production_id=str(raw["production_id"]),
            task_id=str(raw["task_id"]),
            queue_id=str(raw["queue_id"]),
            entry_id=str(raw["entry_id"]),
            resource_id=str(raw["resource_id"]),
            worker_id=str(raw["worker_id"]),
            lease_id=str(raw["lease_id"]),
            attempt_number=_integer(raw["attempt_number"], "attempt_number"),
            authority_fingerprint=str(raw["authority_fingerprint"]),
            provider_id=str(raw["provider_id"]),
            provider_job_id=_optional_string(raw.get("provider_job_id")),
            render_request_id=_optional_string(raw.get("render_request_id")),
            workflow_id=_optional_string(raw.get("workflow_id")),
            state=ProviderExecutionState(str(raw["state"])),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
            updated_at=datetime.fromisoformat(str(raw["updated_at"])),
            submitted_at=_optional_datetime(raw.get("submitted_at")),
            progress=_float(raw.get("progress", 0.0), "progress"),
            failure_reason=_optional_string(raw.get("failure_reason")),
            events=tuple(
                DurableExecutionEvent(
                    state=ProviderExecutionState(str(_mapping(item, "event")["state"])),
                    observed_at=datetime.fromisoformat(
                        str(_mapping(item, "event")["observed_at"])
                    ),
                    progress=_float(_mapping(item, "event").get("progress", 0.0), "progress"),
                    provider_job_id=_optional_string(
                        _mapping(item, "event").get("provider_job_id")
                    ),
                    failure_reason=_optional_string(
                        _mapping(item, "event").get("failure_reason")
                    ),
                )
                for item in events_raw
            ),
        )

    @staticmethod
    def _require_query(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise DurableExecutionJobRepositoryError(f"{field_name} cannot be blank")
        return normalized


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be an object")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} cannot be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"{field_name} must be an integer")


def _float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} cannot be boolean")
    if isinstance(value, int | float | str):
        return float(value)
    raise TypeError(f"{field_name} must be numeric")
