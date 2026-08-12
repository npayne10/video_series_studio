"""Provider-neutral Lighting compilation for Phase 19.4.5."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectNotOpenError, ProjectService


class LightingCompilerError(RuntimeError):
    """Raised when production Lighting authority cannot be processed safely."""


class LightingCompilationStatus(StrEnum):
    """Governance state for reviewed production Lighting authority."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class LightingCompilationDraft:
    """Reviewed provider-neutral Lighting authority for one Production Package."""

    shot_id: str
    source_package_id: str
    source_fingerprint: str
    lighting: dict[str, Any]
    production_notes: str = ""
    status: LightingCompilationStatus = LightingCompilationStatus.DRAFT


class LightingCompilerService:
    """Compile governed Lighting planning into canonical production Lighting intent."""

    FILE_NAME = "lighting_compilation.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService, packages: ProductionPackageService) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[LightingCompilationDraft, ...]:
        path = self.draft_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            drafts = tuple(self._from_dict(item) for item in raw.get("lighting_compilation", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise LightingCompilerError(f"Unable to load Lighting Compiler drafts: {exc}") from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> LightingCompilationDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> LightingCompilationDraft:
        """Seed exactly from governed Lighting planning; never invent Lighting intent."""
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise LightingCompilerError(f"Lighting compilation already exists for {normalized}")
        package = self.packages.current_package(normalized)
        if package is None:
            package = self.packages.materialize(normalized)
        if not package.lighting:
            raise LightingCompilerError("Current Production Package has no governed Lighting plan")
        draft = LightingCompilationDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            lighting=self._detached(package.lighting),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> LightingCompilationDraft:
        """Refresh stale Lighting authority while preserving human production notes."""
        current = self._require_draft(shot_id)
        if current.status is LightingCompilationStatus.READY:
            raise LightingCompilerError(
                "Ready Lighting compilation must return to Draft before refreshing its source"
            )
        package = self.packages.require_current_package(current.shot_id)
        if not package.lighting:
            raise LightingCompilerError("Current Production Package has no governed Lighting plan")
        if current.source_fingerprint == package.source_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            lighting=self._detached(package.lighting),
        )
        self._replace(updated)
        return updated

    def save_notes(self, shot_id: str, production_notes: str) -> LightingCompilationDraft:
        current = self._require_draft(shot_id)
        if current.status is LightingCompilationStatus.READY:
            raise LightingCompilerError(
                "Ready Lighting compilation must return to Draft before editing"
            )
        if not self.is_current(current):
            raise LightingCompilerError(
                "Lighting compilation is stale against the current Production Package"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> LightingCompilationDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise LightingCompilerError(
                "Lighting compilation is stale against the current Production Package"
            )
        self._validate_lighting(current.lighting)
        ready = replace(current, status=LightingCompilationStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> LightingCompilationDraft:
        current = self._require_draft(shot_id)
        draft = replace(current, status=LightingCompilationStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: LightingCompilationDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        return package is not None and package.source_fingerprint == draft.source_fingerprint

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not LightingCompilationStatus.READY:
            raise LightingCompilerError("Only Ready Lighting compilation may be compiled")
        if not self.is_current(draft):
            raise LightingCompilerError("Lighting compilation is stale and cannot be compiled")
        self._validate_lighting(draft.lighting)
        compiled = self._compile_lighting(draft.lighting)
        return self.packages.derive_lighting(
            draft.shot_id,
            compiled,
            production_notes=draft.production_notes,
        )

    @classmethod
    def _compile_lighting(cls, lighting: dict[str, Any]) -> dict[str, Any]:
        governed = cls._detached(lighting)
        return {
            "governed": governed,
            "production": {
                "lighting_intent": governed.get("lighting_intent"),
                "key_direction": governed.get("key_direction"),
                "key_quality": governed.get("key_quality"),
                "color_temperature_k": governed.get("color_temperature_k"),
                "fill_level_percent": governed.get("fill_level_percent"),
                "exposure_intent": governed.get("exposure_intent"),
                "source_strategy": governed.get("source_strategy"),
                "shadow_strategy": governed.get("shadow_strategy"),
                "subject_readability": governed.get("subject_readability"),
                "separation_strategy": governed.get("separation_strategy"),
                "continuity_notes": governed.get("continuity_notes"),
                "lighting_constraints": governed.get("lighting_constraints", []),
                "lighting_profile_asset_id": governed.get("lighting_profile_asset_id", ""),
                "provider_neutral": True,
            },
        }

    @staticmethod
    def _validate_lighting(lighting: dict[str, Any]) -> None:
        required = (
            "lighting_intent",
            "key_direction",
            "key_quality",
            "color_temperature_k",
            "fill_level_percent",
            "exposure_intent",
            "source_strategy",
            "shadow_strategy",
            "subject_readability",
        )
        missing = [key for key in required if lighting.get(key) in (None, "")]
        if missing:
            raise LightingCompilerError(
                "Governed Lighting plan is incomplete: " + ", ".join(sorted(missing))
            )

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise LightingCompilerError("Lighting Compiler value is not a JSON object")
        return dict(decoded)

    def _require_draft(self, shot_id: str) -> LightingCompilationDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise LightingCompilerError(
                f"No Lighting compilation exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: LightingCompilationDraft) -> None:
        drafts = tuple(
            updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
        )
        self._write(drafts)

    def _write(self, drafts: tuple[LightingCompilationDraft, ...]) -> None:
        path = self.draft_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "lighting_compilation": [self._to_dict(item) for item in drafts],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _to_dict(draft: LightingCompilationDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> LightingCompilationDraft:
        lighting = data.get("lighting")
        if not isinstance(lighting, dict):
            raise LightingCompilerError("Lighting Compiler draft Lighting plan is invalid")
        return LightingCompilationDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            source_fingerprint=str(data["source_fingerprint"]),
            lighting=dict(lighting),
            production_notes=str(data.get("production_notes", "")),
            status=LightingCompilationStatus(str(data.get("status", "draft"))),
        )
