"""Durable local persistence for human-governed retry overrides."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from vscs.application.production_execution.retry_override import GovernedRetryAuthorization


class LocalGovernedRetryAuthorizationStore:
    """Schema-versioned project-local persistence for retry authorizations."""

    SCHEMA_VERSION = 1

    def __init__(self, project_directory: Path) -> None:
        authority_root = (
            Path(project_directory).expanduser().resolve(strict=False)
            / ".vscs"
            / "provider_executions"
        )
        self.path = authority_root / "retry_overrides" / "authorizations.json"
        self._legacy_path = authority_root / "retry_overrides.json"
        self._migrate_legacy_store()

    def list_for_task(self, task_id: str) -> tuple[GovernedRetryAuthorization, ...]:
        normalized = task_id.strip()
        if not normalized:
            return ()
        return tuple(item for item in self._load() if item.task_id == normalized)

    def save(self, authorization: GovernedRetryAuthorization) -> GovernedRetryAuthorization:
        existing = list(self._load())
        if any(item.authorization_id == authorization.authorization_id for item in existing):
            raise ValueError(
                f"GovernedRetryAuthorization already exists: {authorization.authorization_id}"
            )
        existing.append(authorization)
        self._write(tuple(existing))
        return authorization

    def _load(self) -> tuple[GovernedRetryAuthorization, ...]:
        if not self.path.is_file():
            return ()
        payload = self._read_payload(self.path)
        items = payload.get("authorizations", [])
        if not isinstance(items, list):
            raise ValueError("retry override authorizations must be a list")
        return tuple(self._decode(item) for item in items)

    def _migrate_legacy_store(self) -> None:
        if not self._legacy_path.is_file():
            return
        legacy = self._decode_payload(self._read_payload(self._legacy_path))
        current = self._decode_payload(self._read_payload(self.path)) if self.path.is_file() else ()
        merged: dict[str, GovernedRetryAuthorization] = {
            item.authorization_id: item for item in current
        }
        for item in legacy:
            existing = merged.get(item.authorization_id)
            if existing is not None and existing != item:
                raise ValueError(
                    "Conflicting governed retry authorization exists in legacy and current stores: "
                    f"{item.authorization_id}"
                )
            merged[item.authorization_id] = item
        self._write(
            tuple(
                sorted(
                    merged.values(),
                    key=lambda item: (
                        item.task_id,
                        item.authorized_attempt_number,
                        item.created_at,
                        item.authorization_id,
                    ),
                )
            )
        )
        self._legacy_path.unlink()

    def _read_payload(self, path: Path) -> dict[str, object]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("governed retry override payload must be an object")
        if payload.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("Unsupported governed retry override schema version")
        return payload

    def _decode_payload(
        self,
        payload: dict[str, object],
    ) -> tuple[GovernedRetryAuthorization, ...]:
        items = payload.get("authorizations", [])
        if not isinstance(items, list):
            raise ValueError("retry override authorizations must be a list")
        return tuple(self._decode(item) for item in items)

    def _write(self, authorizations: tuple[GovernedRetryAuthorization, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "authorizations": [self._encode(item) for item in authorizations],
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
            temp_path = Path(stream.name)
        os.replace(temp_path, self.path)

    @staticmethod
    def _encode(item: GovernedRetryAuthorization) -> dict[str, object]:
        return {
            "authorization_id": item.authorization_id,
            "production_id": item.production_id,
            "task_id": item.task_id,
            "authority_fingerprint": item.authority_fingerprint,
            "authorized_attempt_number": item.authorized_attempt_number,
            "authorized_by": item.authorized_by,
            "reason": item.reason,
            "created_at": item.created_at.isoformat(),
        }

    @staticmethod
    def _decode(payload: object) -> GovernedRetryAuthorization:
        if not isinstance(payload, dict):
            raise ValueError("retry override authorization must be an object")
        return GovernedRetryAuthorization(
            authorization_id=str(payload["authorization_id"]),
            production_id=str(payload["production_id"]),
            task_id=str(payload["task_id"]),
            authority_fingerprint=str(payload["authority_fingerprint"]),
            authorized_attempt_number=int(payload["authorized_attempt_number"]),
            authorized_by=str(payload["authorized_by"]),
            reason=str(payload["reason"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )
