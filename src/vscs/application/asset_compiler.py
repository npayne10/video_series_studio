"""Provider-neutral Asset compilation for Phase 19.4.3."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectNotOpenError, ProjectService


class AssetCompilerError(RuntimeError):
    """Raised when production Asset authority cannot be processed safely."""


class AssetCompilationStatus(StrEnum):
    """Governance state for reviewed production Asset authority."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class AssetCompilationDraft:
    """Reviewed provider-neutral Asset authority for one Production Package."""

    shot_id: str
    source_package_id: str
    source_fingerprint: str
    assets: tuple[dict[str, Any], ...]
    production_notes: str = ""
    status: AssetCompilationStatus = AssetCompilationStatus.DRAFT


class AssetCompilerService:
    """Compile governed Shot Asset bindings into canonical production Asset intent."""

    FILE_NAME = "asset_compilation.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
    ) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[AssetCompilationDraft, ...]:
        path = self.draft_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            drafts = tuple(
                self._from_dict(item) for item in raw.get("asset_compilation", [])
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AssetCompilerError(f"Unable to load Asset Compiler drafts: {exc}") from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> AssetCompilationDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> AssetCompilationDraft:
        """Seed exactly from governed planning Assets; never invent an Asset requirement."""
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise AssetCompilerError(f"Asset compilation already exists for {normalized}")
        package = self.packages.current_package(normalized)
        if package is None:
            package = self.packages.materialize(normalized)
        draft = AssetCompilationDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            assets=tuple(self._detached(item) for item in package.assets),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> AssetCompilationDraft:
        """Refresh stale governed Asset inputs while preserving human production notes."""
        current = self._require_draft(shot_id)
        if current.status is AssetCompilationStatus.READY:
            raise AssetCompilerError(
                "Ready Asset compilation must return to Draft before refreshing its source"
            )
        package = self.packages.require_current_package(current.shot_id)
        if current.source_fingerprint == package.source_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            assets=tuple(self._detached(item) for item in package.assets),
        )
        self._replace(updated)
        return updated

    def save_notes(self, shot_id: str, production_notes: str) -> AssetCompilationDraft:
        current = self._require_draft(shot_id)
        if current.status is AssetCompilationStatus.READY:
            raise AssetCompilerError("Ready Asset compilation must return to Draft before editing")
        if not self.is_current(current):
            raise AssetCompilerError(
                "Asset compilation is stale against the current Production Package"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> AssetCompilationDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise AssetCompilerError(
                "Asset compilation is stale against the current Production Package"
            )
        ready = replace(current, status=AssetCompilationStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> AssetCompilationDraft:
        current = self._require_draft(shot_id)
        draft = replace(current, status=AssetCompilationStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: AssetCompilationDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        return package is not None and package.source_fingerprint == draft.source_fingerprint

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not AssetCompilationStatus.READY:
            raise AssetCompilerError("Only Ready Asset compilation may be compiled")
        if not self.is_current(draft):
            raise AssetCompilerError("Asset compilation is stale and cannot be compiled")
        compiled = tuple(self._compile_asset(item) for item in draft.assets)
        return self.packages.derive_assets(
            draft.shot_id,
            compiled,
            production_notes=draft.production_notes,
        )

    @classmethod
    def _compile_asset(cls, item: dict[str, Any]) -> dict[str, Any]:
        binding_raw = item.get("binding", {})
        resolution_raw = item.get("resolution", {})
        if not isinstance(binding_raw, dict) or not isinstance(resolution_raw, dict):
            raise AssetCompilerError("Governed Asset input is malformed")
        binding = cls._detached(binding_raw)
        resolution = cls._detached(resolution_raw)
        fingerprint = resolution.get("fingerprint", {})
        if not isinstance(fingerprint, dict):
            fingerprint = {}
        production = {
            "asset_id": str(resolution.get("asset_id") or binding.get("asset_id") or ""),
            "binding_id": str(binding.get("binding_id", "")),
            "role": str(binding.get("role", "")),
            "requirement": str(binding.get("requirement", "")),
            "category": str(binding.get("expected_category", "")),
            "canonical_reference": resolution.get("canonical_reference"),
            "dependency_checksum": fingerprint.get("checksum"),
            "provider_neutral": True,
        }
        return {
            "binding": binding,
            "resolution": resolution,
            "production": production,
        }

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise AssetCompilerError("Asset Compiler value is not a JSON object")
        return dict(decoded)

    def _require_draft(self, shot_id: str) -> AssetCompilationDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise AssetCompilerError(
                f"No Asset compilation exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: AssetCompilationDraft) -> None:
        drafts = tuple(
            updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
        )
        self._write(drafts)

    def _write(self, drafts: tuple[AssetCompilationDraft, ...]) -> None:
        path = self.draft_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "asset_compilation": [self._to_dict(item) for item in drafts],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _to_dict(draft: AssetCompilationDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> AssetCompilationDraft:
        raw_assets = data.get("assets", [])
        if not isinstance(raw_assets, list) or not all(
            isinstance(item, dict) for item in raw_assets
        ):
            raise AssetCompilerError("Asset Compiler draft Assets are invalid")
        return AssetCompilationDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            source_fingerprint=str(data["source_fingerprint"]),
            assets=tuple(dict(item) for item in raw_assets),
            production_notes=str(data.get("production_notes", "")),
            status=AssetCompilationStatus(str(data.get("status", "draft"))),
        )
