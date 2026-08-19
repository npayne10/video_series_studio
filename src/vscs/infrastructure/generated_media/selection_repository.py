"""Durable JSON persistence for authoritative Generated Media selections."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from vscs.application.generated_media.selection import (
    GeneratedMediaSelection,
    GeneratedMediaSelectionError,
    GeneratedMediaSelectionEvent,
)
from vscs.domain.generated_media import GeneratedMediaKind


class JsonGeneratedMediaSelectionRepository:
    """Persist one selection document per Generated Media production intent."""

    SCHEMA_VERSION = "1.0"
    _SAFE_ID_CHARACTERS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, selection_id: str) -> GeneratedMediaSelection | None:
        path = self._path(selection_id)
        if not path.exists():
            return None
        return self._read(path)

    def save(self, selection: GeneratedMediaSelection) -> GeneratedMediaSelection:
        path = self._path(selection.selection_id)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "selection": self._to_payload(selection),
        }
        self._write_atomic(path, payload)
        return selection

    def list_for_task(self, production_task_id: str) -> tuple[GeneratedMediaSelection, ...]:
        normalized = production_task_id.strip()
        if not normalized:
            raise GeneratedMediaSelectionError("production_task_id cannot be blank")
        if not self.root.exists():
            return ()
        records = tuple(
            selection
            for path in sorted(self.root.glob("*.json"))
            if (selection := self._read(path)).production_task_id == normalized
        )
        return tuple(sorted(records, key=lambda item: item.selection_id))

    def _path(self, selection_id: str) -> Path:
        normalized = selection_id.strip()
        if not normalized or any(
            character not in self._SAFE_ID_CHARACTERS for character in normalized
        ):
            raise GeneratedMediaSelectionError(
                f"Generated Media selection identity is not filesystem-safe: {selection_id!r}"
            )
        return self.root / f"{normalized}.json"

    def _read(self, path: Path) -> GeneratedMediaSelection:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("selection repository payload must be an object")
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported Generated Media selection schema: "
                    f"{payload.get('schema_version')!r}"
                )
            raw = payload["selection"]
            if not isinstance(raw, dict):
                raise TypeError("selection payload must be an object")
            return self._from_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise GeneratedMediaSelectionError(
                f"Unable to read Generated Media selection document {path}: {exc}"
            ) from exc

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
            raise GeneratedMediaSelectionError(
                f"Unable to persist Generated Media selection {path}: {exc}"
            ) from exc

    @staticmethod
    def _to_payload(selection: GeneratedMediaSelection) -> dict[str, Any]:
        return {
            "selection_id": selection.selection_id,
            "production_id": selection.production_id,
            "episode_id": selection.episode_id,
            "production_task_id": selection.production_task_id,
            "kind": selection.kind.value,
            "selected_media_id": selection.selected_media_id,
            "selected_revision": selection.selected_revision,
            "selected_by": selection.selected_by,
            "reason": selection.reason,
            "selected_at": selection.selected_at.isoformat(),
            "history": [
                {
                    "previous_media_id": event.previous_media_id,
                    "selected_media_id": event.selected_media_id,
                    "selected_revision": event.selected_revision,
                    "actor": event.actor,
                    "reason": event.reason,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in selection.history
            ],
        }

    @staticmethod
    def _from_payload(raw: dict[str, Any]) -> GeneratedMediaSelection:
        history_raw = raw.get("history", [])
        if not isinstance(history_raw, list):
            raise TypeError("selection history must be an array")
        history: list[GeneratedMediaSelectionEvent] = []
        for item in history_raw:
            if not isinstance(item, dict):
                raise TypeError("selection history entries must be objects")
            previous_raw = item.get("previous_media_id")
            history.append(
                GeneratedMediaSelectionEvent(
                    previous_media_id=(
                        str(previous_raw) if previous_raw is not None else None
                    ),
                    selected_media_id=str(item["selected_media_id"]),
                    selected_revision=int(item["selected_revision"]),
                    actor=str(item["actor"]),
                    reason=str(item["reason"]),
                    occurred_at=datetime.fromisoformat(str(item["occurred_at"])),
                )
            )
        return GeneratedMediaSelection(
            selection_id=str(raw["selection_id"]),
            production_id=str(raw["production_id"]),
            episode_id=str(raw["episode_id"]),
            production_task_id=str(raw["production_task_id"]),
            kind=GeneratedMediaKind(str(raw["kind"])),
            selected_media_id=str(raw["selected_media_id"]),
            selected_revision=int(raw["selected_revision"]),
            selected_by=str(raw["selected_by"]),
            reason=str(raw["reason"]),
            selected_at=datetime.fromisoformat(str(raw["selected_at"])),
            history=tuple(history),
        )
