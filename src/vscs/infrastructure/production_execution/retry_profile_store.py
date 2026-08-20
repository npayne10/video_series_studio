"""Durable profile scope for Phase 20.16.1 retry authorizations."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from vscs.application.production_execution import normalize_execution_profile


@dataclass(frozen=True, slots=True)
class RetryAuthorizationProfile:
    authorization_id: str
    task_id: str
    profile: str

    def __post_init__(self) -> None:
        if not self.authorization_id.strip():
            raise ValueError("authorization_id cannot be blank")
        if not self.task_id.strip():
            raise ValueError("task_id cannot be blank")
        object.__setattr__(self, "profile", normalize_execution_profile(self.profile))


class LocalRetryAuthorizationProfileStore:
    """Associate retry authority with one execution profile; legacy authority is production."""

    SCHEMA_VERSION = 1

    def __init__(self, project_directory: Path) -> None:
        self.path = (
            Path(project_directory).expanduser().resolve(strict=False)
            / ".vscs"
            / "provider_executions"
            / "retry_overrides"
            / "profiles.json"
        )

    def assign(self, authorization_id: str, task_id: str, profile: str) -> RetryAuthorizationProfile:
        assignment = RetryAuthorizationProfile(authorization_id, task_id, profile)
        existing = list(self._load())
        current = next(
            (item for item in existing if item.authorization_id == assignment.authorization_id),
            None,
        )
        if current is not None:
            if current != assignment:
                raise ValueError(
                    "Retry authorization profile conflicts with existing durable scope: "
                    f"{authorization_id}"
                )
            return current
        existing.append(assignment)
        self._write(tuple(existing))
        return assignment

    def profile_for_authorization(self, authorization_id: str) -> str:
        normalized = authorization_id.strip()
        assignment = next(
            (item for item in self._load() if item.authorization_id == normalized),
            None,
        )
        return assignment.profile if assignment is not None else "production"

    def _load(self) -> tuple[RetryAuthorizationProfile, ...]:
        if not self.path.is_file():
            return ()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("Unsupported retry authorization profile schema")
        raw = payload.get("assignments", [])
        if not isinstance(raw, list):
            raise ValueError("retry authorization profile assignments must be a list")
        return tuple(self._decode(item) for item in raw)

    def _write(self, assignments: tuple[RetryAuthorizationProfile, ...]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "assignments": [
                {
                    "authorization_id": item.authorization_id,
                    "task_id": item.task_id,
                    "profile": item.profile,
                }
                for item in assignments
            ],
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
    def _decode(payload: object) -> RetryAuthorizationProfile:
        if not isinstance(payload, dict):
            raise ValueError("retry authorization profile assignment must be an object")
        return RetryAuthorizationProfile(
            authorization_id=str(payload["authorization_id"]),
            task_id=str(payload["task_id"]),
            profile=str(payload["profile"]),
        )
