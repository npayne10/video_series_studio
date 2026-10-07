"""Persist governed provider-policy selections for normal Production Execution."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from vscs.application.production_execution.profiles import normalize_execution_profile
from vscs.application.production_execution.provider_policy_profiles import ProviderPolicyProfile

from .provider_policy_profiles import (
    LTX25_CANDIDATE_C_POLICY_PROFILE_ID,
    default_provider_policy_profile_registry,
)


class ProviderPolicySelectionError(RuntimeError):
    """Raised when persisted provider-policy selection authority is invalid."""


@dataclass(frozen=True, slots=True)
class ProviderPolicySelection:
    task_id: str
    execution_profile: str
    provider_profile_id: str
    provider_profile_fingerprint: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        task_id = self.task_id.strip()
        if not task_id:
            raise ProviderPolicySelectionError("Provider-policy selection requires task_id")
        object.__setattr__(self, "task_id", task_id)
        object.__setattr__(
            self,
            "execution_profile",
            normalize_execution_profile(self.execution_profile),
        )
        for field_name in ("provider_profile_id", "provider_profile_fingerprint"):
            value = str(getattr(self, field_name)).strip().lower()
            if not value:
                raise ProviderPolicySelectionError(
                    f"Provider-policy selection requires {field_name}"
                )
            object.__setattr__(self, field_name, value)
        if self.schema_version != "1.0":
            raise ProviderPolicySelectionError(
                "Provider-policy selection requires schema version 1.0"
            )

    @property
    def key(self) -> str:
        return f"{self.task_id}|{self.execution_profile}"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class ProviderPolicySelectionStore:
    """Project-local selected provider profile per task and execution profile."""

    SOURCE = Path(".vscs") / "production_execution" / "provider_policy_selections.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.path = self.project_directory / self.SOURCE
        self.registry = default_provider_policy_profile_registry()

    def selected_profile(
        self,
        task_id: str,
        execution_profile: str,
    ) -> ProviderPolicyProfile:
        task = task_id.strip()
        profile = normalize_execution_profile(execution_profile)
        selection = self._records().get(f"{task}|{profile}")
        if selection is None:
            return self.registry.require(LTX25_CANDIDATE_C_POLICY_PROFILE_ID)
        provider_profile = self.registry.require(selection.provider_profile_id)
        if provider_profile.fingerprint != selection.provider_profile_fingerprint:
            raise ProviderPolicySelectionError(
                "Persisted provider-policy selection fingerprint is stale: "
                f"{selection.provider_profile_id}"
            )
        return provider_profile

    def select(
        self,
        task_id: str,
        execution_profile: str,
        provider_profile_id: str,
    ) -> ProviderPolicyProfile:
        task = task_id.strip()
        if not task:
            raise ProviderPolicySelectionError("Provider-policy selection requires task_id")
        profile = normalize_execution_profile(execution_profile)
        provider_profile = self.registry.require(provider_profile_id)
        records = self._records()
        selection = ProviderPolicySelection(
            task_id=task,
            execution_profile=profile,
            provider_profile_id=provider_profile.profile_id,
            provider_profile_fingerprint=provider_profile.fingerprint,
        )
        records[selection.key] = selection
        self._write(records)
        return provider_profile

    def _records(self) -> dict[str, ProviderPolicySelection]:
        if not self.path.is_file():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProviderPolicySelectionError(
                f"Cannot read provider-policy selections: {exc}"
            ) from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != "1.0":
            raise ProviderPolicySelectionError(
                "Provider-policy selection store has unsupported schema"
            )
        values = raw.get("selections", [])
        if not isinstance(values, list):
            raise ProviderPolicySelectionError(
                "Provider-policy selection store selections must be an array"
            )
        result: dict[str, ProviderPolicySelection] = {}
        for item in values:
            if not isinstance(item, dict):
                raise ProviderPolicySelectionError(
                    "Provider-policy selection records must be objects"
                )
            record = ProviderPolicySelection(
                task_id=str(item.get("task_id", "")),
                execution_profile=str(item.get("execution_profile", "")),
                provider_profile_id=str(item.get("provider_profile_id", "")),
                provider_profile_fingerprint=str(
                    item.get("provider_profile_fingerprint", "")
                ),
                schema_version=str(item.get("schema_version", "")),
            )
            if record.key in result:
                raise ProviderPolicySelectionError(
                    f"Duplicate provider-policy selection: {record.key}"
                )
            result[record.key] = record
        return result

    def _write(self, records: dict[str, ProviderPolicySelection]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "selections": [
                records[key].to_dict()
                for key in sorted(records)
            ],
        }
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)
