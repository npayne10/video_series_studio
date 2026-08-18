"""Durable JSON persistence for provider registrations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from vscs.application.production_tasks import ProductionCapability, ProductionTaskType
from vscs.application.provider_execution.provider_registry import (
    ProviderHealthState,
    ProviderRegistration,
    ProviderRegistrationState,
)
from vscs.application.provider_execution.provider_repository import (
    ProviderRegistrationRepositoryError,
)
from vscs.domain.generated_media import GeneratedMediaKind


class JsonProviderRegistrationRepository:
    """Persist one provider registration JSON document per stable provider identity."""

    SCHEMA_VERSION = "1.0"
    _SAFE_ID_CHARACTERS = frozenset(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get(self, provider_id: str) -> ProviderRegistration | None:
        normalized = self._require_query(provider_id, "provider_id")
        path = self._path(normalized)
        if not path.exists():
            return None
        return self._read(path)

    def save(self, provider: ProviderRegistration) -> ProviderRegistration:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "provider": self._to_payload(provider),
        }
        self._write_atomic(self._path(provider.provider_id), payload)
        return provider

    def list_all(self) -> tuple[ProviderRegistration, ...]:
        if not self.root.exists():
            return ()
        providers = tuple(self._read(path) for path in sorted(self.root.glob("*.json")))
        return tuple(sorted(providers, key=lambda item: item.provider_id))

    def list_for_resource(self, resource_id: str) -> tuple[ProviderRegistration, ...]:
        normalized = self._require_query(resource_id, "resource_id")
        return tuple(provider for provider in self.list_all() if provider.resource_id == normalized)

    def _read(self, path: Path) -> ProviderRegistration:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise TypeError("repository payload must be an object")
            if payload.get("schema_version") != self.SCHEMA_VERSION:
                raise ValueError(
                    f"Unsupported provider registry schema: {payload.get('schema_version')!r}"
                )
            raw = payload["provider"]
            if not isinstance(raw, dict):
                raise TypeError("provider payload must be an object")
            return self._from_payload(raw)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ProviderRegistrationRepositoryError(
                f"Unable to read provider registration {path}: {exc}"
            ) from exc

    def _path(self, provider_id: str) -> Path:
        normalized = provider_id.strip()
        if not normalized or any(
            character not in self._SAFE_ID_CHARACTERS for character in normalized
        ):
            raise ProviderRegistrationRepositoryError(
                f"Provider identity is not filesystem-safe: {provider_id!r}"
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
            raise ProviderRegistrationRepositoryError(
                f"Unable to persist provider registration {path}: {exc}"
            ) from exc

    @staticmethod
    def _to_payload(provider: ProviderRegistration) -> dict[str, Any]:
        return {
            "provider_id": provider.provider_id,
            "adapter_type": provider.adapter_type,
            "resource_id": provider.resource_id,
            "capabilities": sorted(item.value for item in provider.capabilities),
            "supported_task_types": sorted(item.value for item in provider.supported_task_types),
            "supported_media_kinds": sorted(item.value for item in provider.supported_media_kinds),
            "endpoint": provider.endpoint,
            "secret_reference": provider.secret_reference,
            "state": provider.state.value,
            "health": provider.health.value,
            "configuration": [list(item) for item in provider.configuration],
            "metadata": [list(item) for item in provider.metadata],
        }

    @staticmethod
    def _from_payload(raw: dict[str, Any]) -> ProviderRegistration:
        return ProviderRegistration(
            provider_id=str(raw["provider_id"]),
            adapter_type=str(raw["adapter_type"]),
            resource_id=str(raw["resource_id"]),
            capabilities=frozenset(
                ProductionCapability(str(item))
                for item in _list(raw["capabilities"], "capabilities")
            ),
            supported_task_types=frozenset(
                ProductionTaskType(str(item))
                for item in _list(raw["supported_task_types"], "supported_task_types")
            ),
            supported_media_kinds=frozenset(
                GeneratedMediaKind(str(item))
                for item in _list(raw["supported_media_kinds"], "supported_media_kinds")
            ),
            endpoint=_optional_string(raw.get("endpoint")),
            secret_reference=_optional_string(raw.get("secret_reference")),
            state=ProviderRegistrationState(str(raw["state"])),
            health=ProviderHealthState(str(raw["health"])),
            configuration=_pairs(raw.get("configuration", []), "configuration"),
            metadata=_pairs(raw.get("metadata", []), "metadata"),
        )

    @staticmethod
    def _require_query(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ProviderRegistrationRepositoryError(f"{field_name} cannot be blank")
        return normalized


def _list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be an array")
    return value


def _pairs(value: object, field_name: str) -> tuple[tuple[str, str], ...]:
    values = _list(value, field_name)
    pairs: list[tuple[str, str]] = []
    for item in values:
        if not isinstance(item, list) or len(item) != 2:
            raise TypeError(f"{field_name} entries must be two-item arrays")
        pairs.append((str(item[0]), str(item[1])))
    return tuple(pairs)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
