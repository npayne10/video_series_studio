"""Read/write access to persisted governed shot reference plans."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from vscs.application.acpp.serialization import ACPPSerializationError, ACPPSerializer
from vscs.application.projects import ProjectNotOpenError, ProjectService


class GovernedReferencePlanSourceError(RuntimeError):
    """Raised when persisted governed reference authority cannot be read safely."""


class GovernedReferencePlanSource(Protocol):
    """Provide the authoritative persisted reference-plan payload for one Shot."""

    def reference_plan_for_shot(self, shot_id: str) -> dict[str, Any] | None: ...


class PersistedGovernedReferencePlanSource:
    """Resolve governed reference plans from durable production authority.

    Phase 20.18.1 originally read editable ACPP records from ``story/acpp``. Real
    projects do not persist ACPP records there, so Phase 20.18.2 promotes governed
    shot plans into their own production-authority store while retaining the old
    ACPP lookup as a read-only compatibility fallback.
    """

    FILE_NAME = "governed_reference_plans.json"
    LEGACY_DIRECTORY_NAME = "acpp"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        serializer: ACPPSerializer | None = None,
    ) -> None:
        self.projects = projects
        self.serializer = serializer or ACPPSerializer()

    @property
    def project_directory(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory

    @property
    def store_file(self) -> Path:
        return self.project_directory / "production" / self.FILE_NAME

    @property
    def legacy_package_directory(self) -> Path:
        return self.project_directory / "story" / self.LEGACY_DIRECTORY_NAME

    @property
    def compiled_package_directory(self) -> Path:
        return self.project_directory / "production" / "compiled"

    def reference_plan_for_shot(self, shot_id: str) -> dict[str, Any] | None:
        normalized = shot_id.strip().upper()
        if not normalized:
            return None
        persisted = self._persisted_reference_plan(normalized)
        if persisted is not None:
            return persisted
        legacy = self._legacy_reference_plan(normalized)
        if legacy is not None:
            return legacy
        if self._has_legacy_compiled_reference_authority(normalized):
            raise GovernedReferencePlanSourceError(
                f"Legacy reference authority exists for {normalized}, but no Phase 20.18.1 "
                "governed reference plan has been persisted. Explicit governed migration "
                "and provider-ready validation are required before UPD compilation."
            )
        return None

    def save_reference_plan(
        self,
        shot_id: str,
        reference_plan: dict[str, Any],
        *,
        provenance: dict[str, Any] | None = None,
    ) -> None:
        """Persist one governed shot plan without weakening its suitability facts."""
        normalized = shot_id.strip().upper()
        if not normalized:
            raise GovernedReferencePlanSourceError("Governed reference plan requires a Shot ID")
        self._validate_plan(reference_plan, normalized)
        payload = self._load_store()
        records_raw = payload.get("governed_reference_plans", [])
        records = [dict(item) for item in records_raw if isinstance(item, dict)]
        record = {
            "shot_id": normalized,
            "reference_plan": self._detached(reference_plan),
            "provenance": self._detached(provenance or {}),
        }
        records = [item for item in records if str(item.get("shot_id") or "").upper() != normalized]
        records.append(record)
        records.sort(key=lambda item: str(item.get("shot_id") or ""))
        output = {
            "schema_version": self.SCHEMA_VERSION,
            "governed_reference_plans": records,
        }
        path = self.store_file
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError as exc:
            raise GovernedReferencePlanSourceError(
                f"Unable to persist governed reference authority: {exc}"
            ) from exc

    def _persisted_reference_plan(self, shot_id: str) -> dict[str, Any] | None:
        payload = self._load_store()
        records = payload.get("governed_reference_plans", [])
        if not isinstance(records, list):
            raise GovernedReferencePlanSourceError(
                "governed_reference_plans must be a JSON array"
            )
        for item in records:
            if not isinstance(item, dict):
                continue
            if str(item.get("shot_id") or "").strip().upper() != shot_id:
                continue
            plan = item.get("reference_plan")
            if not isinstance(plan, dict):
                raise GovernedReferencePlanSourceError(
                    f"Persisted governed reference plan for {shot_id} is invalid"
                )
            self._validate_plan(plan, shot_id)
            return self._detached(plan)
        return None

    def _legacy_reference_plan(self, shot_id: str) -> dict[str, Any] | None:
        directory = self.legacy_package_directory
        if not directory.is_dir():
            return None
        match = None
        for path in sorted(directory.glob("*.json")):
            try:
                package = self.serializer.loads(path.read_text(encoding="utf-8"))
            except (OSError, ACPPSerializationError) as exc:
                raise GovernedReferencePlanSourceError(
                    f"Unable to read governed reference authority from {path.name}: {exc}"
                ) from exc
            if package.identity.shot_id.strip().upper() == shot_id:
                match = package
                break
        if match is None or match.reference_plan is None:
            return None
        payload = self.serializer.to_dict(match).get("reference_plan")
        if not isinstance(payload, dict):
            raise GovernedReferencePlanSourceError(
                f"Persisted governed reference plan for {shot_id} is invalid"
            )
        return dict(payload)

    def _has_legacy_compiled_reference_authority(self, shot_id: str) -> bool:
        directory = self.compiled_package_directory
        if not directory.is_dir():
            return False
        for path in sorted(directory.glob("*/*/*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            reference_plan = raw.get("reference_plan")
            if not isinstance(reference_plan, dict):
                continue
            if str(reference_plan.get("schema_version") or "") != "1.1":
                continue
            task = raw.get("task")
            task_shot_id = ""
            if isinstance(task, dict):
                task_shot_id = str(task.get("shot_id") or "").strip().upper()
            composition = raw.get("composition_plan")
            composition_shot_id = ""
            if isinstance(composition, dict):
                composition_shot_id = str(composition.get("shot_id") or "").strip().upper()
            if shot_id in {task_shot_id, composition_shot_id}:
                return True
        return False

    def _load_store(self) -> dict[str, Any]:
        path = self.store_file
        if not path.is_file():
            return {
                "schema_version": self.SCHEMA_VERSION,
                "governed_reference_plans": [],
            }
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernedReferencePlanSourceError(
                f"Unable to read governed reference authority from {path.name}: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise GovernedReferencePlanSourceError(
                "Governed reference plan store must be a JSON object"
            )
        return raw

    @staticmethod
    def _validate_plan(reference_plan: dict[str, Any], shot_id: str) -> None:
        references = reference_plan.get("references")
        if not isinstance(references, list):
            raise GovernedReferencePlanSourceError(
                f"Persisted governed reference plan for {shot_id} must contain references"
            )
        target = reference_plan.get("target")
        if target is not None and not isinstance(target, dict):
            raise GovernedReferencePlanSourceError(
                f"Persisted governed reference plan target for {shot_id} is invalid"
            )

    @staticmethod
    def _detached(value: Any) -> Any:
        return json.loads(json.dumps(value, default=str))
