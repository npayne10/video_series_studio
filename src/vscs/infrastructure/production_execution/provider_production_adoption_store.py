"""Persist provider-selectable production readiness and adoption evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.production_execution import ProviderExecutionReadiness


class ProviderProductionAdoptionError(RuntimeError):
    """Raised when provider adoption evidence cannot be persisted safely."""


@dataclass(frozen=True, slots=True)
class ProviderProductionAdoptionRecord:
    task_id: str
    shot_id: str
    execution_profile: str
    provider_profile_id: str
    provider_profile_fingerprint: str
    execution_adapter_id: str
    package_fingerprint: str
    readiness_id: str
    readiness_fingerprint: str
    state: str
    final_path: str | None = None
    final_frame_count: int | None = None
    approved_by: str | None = None
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        for field_name in (
            "task_id",
            "shot_id",
            "execution_profile",
            "provider_profile_id",
            "provider_profile_fingerprint",
            "execution_adapter_id",
            "package_fingerprint",
            "readiness_id",
            "readiness_fingerprint",
            "state",
        ):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ProviderProductionAdoptionError(
                    f"Provider adoption record requires {field_name}"
                )
            object.__setattr__(self, field_name, value)
        if self.final_frame_count is not None and self.final_frame_count <= 0:
            raise ProviderProductionAdoptionError(
                "Provider adoption final_frame_count must be positive"
            )
        if self.schema_version != "1.0":
            raise ProviderProductionAdoptionError(
                "Provider adoption record requires schema version 1.0"
            )

    @property
    def key(self) -> str:
        return f"{self.task_id}|{self.execution_profile}"

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "shot_id": self.shot_id,
            "execution_profile": self.execution_profile,
            "provider_profile_id": self.provider_profile_id,
            "provider_profile_fingerprint": self.provider_profile_fingerprint,
            "execution_adapter_id": self.execution_adapter_id,
            "package_fingerprint": self.package_fingerprint,
            "readiness_id": self.readiness_id,
            "readiness_fingerprint": self.readiness_fingerprint,
            "state": self.state,
            "final_path": self.final_path,
            "final_frame_count": self.final_frame_count,
            "approved_by": self.approved_by,
        }


class ProviderProductionAdoptionStore:
    """Project-local audit for provider readiness and first real-shot adoption."""

    READINESS_PATH = Path(".vscs") / "production_execution" / "provider_execution_readiness.json"
    ADOPTION_PATH = Path(".vscs") / "production_execution" / "provider_production_adoptions.json"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.readiness_path = self.project_directory / self.READINESS_PATH
        self.adoption_path = self.project_directory / self.ADOPTION_PATH

    def save_readiness(self, readiness: ProviderExecutionReadiness) -> ProviderExecutionReadiness:
        root = self._read_root(self.readiness_path, "readiness")
        raw_records = root.get("records", [])
        if not isinstance(raw_records, list):
            raise ProviderProductionAdoptionError("Provider readiness records must be an array")
        records = {self._record_key(item): item for item in raw_records if isinstance(item, dict)}
        records[f"{readiness.task_id}|{readiness.execution_profile}"] = readiness.to_dict()
        self._write_root(self.readiness_path, records)
        return readiness

    def adoption_for(
        self,
        task_id: str,
        execution_profile: str,
    ) -> ProviderProductionAdoptionRecord | None:
        root = self._read_root(self.adoption_path, "adoption")
        key = f"{task_id.strip()}|{execution_profile.strip().lower()}"
        raw_records = root.get("records", [])
        if not isinstance(raw_records, list):
            raise ProviderProductionAdoptionError("Provider adoption records must be an array")
        for item in reversed(raw_records):
            if not isinstance(item, dict) or self._record_key(item) != key:
                continue
            return self._adoption_from_dict(item)
        return None

    def record_generated(
        self,
        readiness: ProviderExecutionReadiness,
        *,
        final_path: str | None,
        final_frame_count: int | None,
        state: str,
    ) -> ProviderProductionAdoptionRecord:
        record = ProviderProductionAdoptionRecord(
            task_id=readiness.task_id,
            shot_id=readiness.shot_id,
            execution_profile=readiness.execution_profile,
            provider_profile_id=readiness.provider_profile_id,
            provider_profile_fingerprint=readiness.provider_profile_fingerprint,
            execution_adapter_id=readiness.execution_adapter_id,
            package_fingerprint=readiness.package_fingerprint,
            readiness_id=readiness.readiness_id,
            readiness_fingerprint=readiness.fingerprint,
            state=state,
            final_path=final_path,
            final_frame_count=final_frame_count,
        )
        self._save_adoption(record)
        return record

    def mark_accepted(
        self,
        task_id: str,
        execution_profile: str,
        *,
        approved_by: str,
        final_path: str | None,
        final_frame_count: int | None,
    ) -> ProviderProductionAdoptionRecord:
        current = self.adoption_for(task_id, execution_profile)
        if current is None:
            raise ProviderProductionAdoptionError(
                "Cannot accept provider production before generated adoption evidence exists"
            )
        actor = approved_by.strip()
        if not actor:
            raise ProviderProductionAdoptionError(
                "Provider production acceptance requires a human reviewer"
            )
        record = ProviderProductionAdoptionRecord(
            task_id=current.task_id,
            shot_id=current.shot_id,
            execution_profile=current.execution_profile,
            provider_profile_id=current.provider_profile_id,
            provider_profile_fingerprint=current.provider_profile_fingerprint,
            execution_adapter_id=current.execution_adapter_id,
            package_fingerprint=current.package_fingerprint,
            readiness_id=current.readiness_id,
            readiness_fingerprint=current.readiness_fingerprint,
            state="accepted",
            final_path=final_path or current.final_path,
            final_frame_count=final_frame_count or current.final_frame_count,
            approved_by=actor,
        )
        self._save_adoption(record)
        return record

    def _save_adoption(self, record: ProviderProductionAdoptionRecord) -> None:
        root = self._read_root(self.adoption_path, "adoption")
        raw_records = root.get("records", [])
        if not isinstance(raw_records, list):
            raise ProviderProductionAdoptionError("Provider adoption records must be an array")
        records = {self._record_key(item): item for item in raw_records if isinstance(item, dict)}
        records[record.key] = record.to_dict()
        self._write_root(self.adoption_path, records)

    @staticmethod
    def _record_key(item: dict[str, object]) -> str:
        return (
            f"{str(item.get('task_id') or '').strip()}|"
            f"{str(item.get('execution_profile') or '').strip().lower()}"
        )

    @staticmethod
    def _adoption_from_dict(item: dict[str, object]) -> ProviderProductionAdoptionRecord:
        return ProviderProductionAdoptionRecord(
            task_id=str(item.get("task_id") or ""),
            shot_id=str(item.get("shot_id") or ""),
            execution_profile=str(item.get("execution_profile") or ""),
            provider_profile_id=str(item.get("provider_profile_id") or ""),
            provider_profile_fingerprint=str(item.get("provider_profile_fingerprint") or ""),
            execution_adapter_id=str(item.get("execution_adapter_id") or ""),
            package_fingerprint=str(item.get("package_fingerprint") or ""),
            readiness_id=str(item.get("readiness_id") or ""),
            readiness_fingerprint=str(item.get("readiness_fingerprint") or ""),
            state=str(item.get("state") or ""),
            final_path=(
                None if item.get("final_path") is None else str(item.get("final_path") or "")
            ),
            final_frame_count=(
                None
                if item.get("final_frame_count") is None
                else int(str(item["final_frame_count"]))
            ),
            approved_by=(
                None if item.get("approved_by") is None else str(item.get("approved_by") or "")
            ),
            schema_version=str(item.get("schema_version") or ""),
        )

    @staticmethod
    def _read_root(path: Path, label: str) -> dict[str, object]:
        if not path.is_file():
            return {"schema_version": "1.0", "records": []}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ProviderProductionAdoptionError(
                f"Cannot read provider {label} evidence: {exc}"
            ) from exc
        if (
            not isinstance(raw, dict)
            or raw.get("schema_version") != "1.0"
            or not isinstance(raw.get("records", []), list)
        ):
            raise ProviderProductionAdoptionError(f"Provider {label} evidence store is invalid")
        return raw

    @staticmethod
    def _write_root(
        path: Path,
        records: dict[str, dict[str, object]],
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "records": [records[key] for key in sorted(records)],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
