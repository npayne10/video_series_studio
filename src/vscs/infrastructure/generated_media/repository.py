"""Durable JSON persistence adapter for authoritative Generated Media records."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from vscs.application.generated_media import GeneratedMediaRepositoryError
from vscs.domain.generated_media import (
    GeneratedMedia,
    GeneratedMediaFile,
    GeneratedMediaGovernanceEvent,
    GeneratedMediaKind,
    GeneratedMediaProvenance,
    GeneratedMediaScope,
    GeneratedMediaState,
)


class JsonGeneratedMediaRepository:
    """Persist one authoritative Generated Media JSON document per stable identity."""

    SCHEMA_VERSION = "1.0"
    _SAFE_ID_CHARACTERS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, media_id: str) -> GeneratedMedia | None:
        normalized = self._require_query(media_id, "media_id")
        path = self._path(normalized)
        if not path.exists():
            return None
        return self._read(path)

    def save(self, media: GeneratedMedia) -> GeneratedMedia:
        """Atomically create or replace one authoritative Generated Media document."""
        path = self._path(media.media_id)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "generated_media": self._to_payload(media),
        }
        self._write_atomic(path, payload)
        return media

    def list_for_production(self, production_id: str) -> tuple[GeneratedMedia, ...]:
        normalized = self._require_query(production_id, "production_id")
        return self._matching(lambda media: media.scope.production_id == normalized)

    def list_for_episode(
        self,
        production_id: str,
        episode_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        production = self._require_query(production_id, "production_id")
        episode = self._require_query(episode_id, "episode_id")
        return self._matching(
            lambda media: media.scope.production_id == production
            and media.scope.episode_id == episode
        )

    def list_for_scene(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        production = self._require_query(production_id, "production_id")
        episode = self._require_query(episode_id, "episode_id")
        scene = self._require_query(scene_id, "scene_id")
        return self._matching(
            lambda media: media.scope.production_id == production
            and media.scope.episode_id == episode
            and media.scope.scene_id == scene
        )

    def list_for_shot(
        self,
        production_id: str,
        episode_id: str,
        scene_id: str,
        shot_id: str,
    ) -> tuple[GeneratedMedia, ...]:
        production = self._require_query(production_id, "production_id")
        episode = self._require_query(episode_id, "episode_id")
        scene = self._require_query(scene_id, "scene_id")
        shot = self._require_query(shot_id, "shot_id")
        return self._matching(
            lambda media: media.scope.production_id == production
            and media.scope.episode_id == episode
            and media.scope.scene_id == scene
            and media.scope.shot_id == shot
        )

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMedia, ...]:
        task_id = self._require_query(production_task_id, "production_task_id")
        return self._matching(lambda media: media.scope.production_task_id == task_id)

    def list_for_execution(self, execution_id: str) -> tuple[GeneratedMedia, ...]:
        normalized = self._require_query(execution_id, "execution_id")
        return self._matching(lambda media: media.provenance.execution_id == normalized)

    def _matching(self, predicate: Any) -> tuple[GeneratedMedia, ...]:
        if not self.root.exists():
            return ()
        records = tuple(
            media
            for path in sorted(self.root.glob("*.json"))
            if (media := self._read(path)) is not None and predicate(media)
        )
        return tuple(sorted(records, key=lambda item: item.media_id))

    def _read(self, path: Path) -> GeneratedMedia:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("repository payload must be an object")
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported Generated Media repository schema: "
                    f"{payload.get('schema_version')!r}"
                )
            raw = payload["generated_media"]
            if not isinstance(raw, dict):
                raise TypeError("generated_media payload must be an object")
            return self._from_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise GeneratedMediaRepositoryError(
                f"Unable to read Generated Media document {path}: {exc}"
            ) from exc

    def _path(self, media_id: str) -> Path:
        normalized = media_id.strip()
        if not normalized or any(
            character not in self._SAFE_ID_CHARACTERS for character in normalized
        ):
            raise GeneratedMediaRepositoryError(
                f"Generated Media identity is not filesystem-safe: {media_id!r}"
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
            raise GeneratedMediaRepositoryError(
                f"Unable to persist Generated Media data {path}: {exc}"
            ) from exc

    @staticmethod
    def _to_payload(media: GeneratedMedia) -> dict[str, Any]:
        return {
            "media_id": media.media_id,
            "kind": media.kind.value,
            "scope": {
                "production_id": media.scope.production_id,
                "episode_id": media.scope.episode_id,
                "scene_id": media.scope.scene_id,
                "shot_id": media.scope.shot_id,
                "production_task_id": media.scope.production_task_id,
            },
            "provenance": {
                "execution_id": media.provenance.execution_id,
                "provider_id": media.provenance.provider_id,
                "provider_job_id": media.provenance.provider_job_id,
                "render_request_id": media.provenance.render_request_id,
                "render_output_id": media.provenance.render_output_id,
                "workflow_id": media.provenance.workflow_id,
                "queue_entry_id": media.provenance.queue_entry_id,
                "worker_id": media.provenance.worker_id,
                "attributes": [list(value) for value in media.provenance.attributes],
            },
            "file": {
                "relative_path": media.file.relative_path,
                "checksum_sha256": media.file.checksum_sha256,
                "size_bytes": media.file.size_bytes,
            },
            "state": media.state.value,
            "revision": media.revision,
            "technical_metadata": [list(value) for value in media.technical_metadata],
            "governance_history": [
                {
                    "from_state": event.from_state.value,
                    "to_state": event.to_state.value,
                    "actor": event.actor,
                    "reason": event.reason,
                    "occurred_at": event.occurred_at.isoformat(),
                    "replacement_media_id": event.replacement_media_id,
                }
                for event in media.governance_history
            ],
            "created_at": media.created_at.isoformat(),
        }

    @staticmethod
    def _from_payload(raw: dict[str, Any]) -> GeneratedMedia:
        scope_raw = _mapping(raw["scope"], "scope")
        provenance_raw = _mapping(raw["provenance"], "provenance")
        file_raw = _mapping(raw["file"], "file")
        history_raw = raw.get("governance_history", [])
        if not isinstance(history_raw, list):
            raise TypeError("governance_history must be an array")
        return GeneratedMedia(
            media_id=str(raw["media_id"]),
            kind=GeneratedMediaKind(str(raw["kind"])),
            scope=GeneratedMediaScope(
                production_id=str(scope_raw["production_id"]),
                episode_id=str(scope_raw["episode_id"]),
                scene_id=_optional_string(scope_raw.get("scene_id")),
                shot_id=_optional_string(scope_raw.get("shot_id")),
                production_task_id=str(scope_raw["production_task_id"]),
            ),
            provenance=GeneratedMediaProvenance(
                execution_id=str(provenance_raw["execution_id"]),
                provider_id=str(provenance_raw["provider_id"]),
                provider_job_id=str(provenance_raw["provider_job_id"]),
                render_request_id=_optional_string(provenance_raw.get("render_request_id")),
                render_output_id=_optional_string(provenance_raw.get("render_output_id")),
                workflow_id=_optional_string(provenance_raw.get("workflow_id")),
                queue_entry_id=_optional_string(provenance_raw.get("queue_entry_id")),
                worker_id=_optional_string(provenance_raw.get("worker_id")),
                attributes=_pairs(provenance_raw.get("attributes", []), "attributes"),
            ),
            file=GeneratedMediaFile(
                relative_path=str(file_raw["relative_path"]),
                checksum_sha256=_optional_string(file_raw.get("checksum_sha256")),
                size_bytes=_optional_int(file_raw.get("size_bytes")),
            ),
            state=GeneratedMediaState(str(raw["state"])),
            revision=int(raw["revision"]),
            technical_metadata=_pairs(raw.get("technical_metadata", []), "technical_metadata"),
            governance_history=tuple(
                GeneratedMediaGovernanceEvent(
                    from_state=GeneratedMediaState(str(_mapping(item, "governance event")["from_state"])),
                    to_state=GeneratedMediaState(str(_mapping(item, "governance event")["to_state"])),
                    actor=str(_mapping(item, "governance event")["actor"]),
                    reason=str(_mapping(item, "governance event")["reason"]),
                    occurred_at=datetime.fromisoformat(
                        str(_mapping(item, "governance event")["occurred_at"])
                    ),
                    replacement_media_id=_optional_string(
                        _mapping(item, "governance event").get("replacement_media_id")
                    ),
                )
                for item in history_raw
            ),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )

    @staticmethod
    def _require_query(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise GeneratedMediaRepositoryError(f"{field_name} cannot be blank")
        return normalized


def _mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{field_name} must be an object")
    return value


def _pairs(value: object, field_name: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be an array")
    pairs: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise TypeError(f"{field_name} entries must be two-item arrays")
        pairs.append((str(item[0]), str(item[1])))
    return tuple(pairs)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)
