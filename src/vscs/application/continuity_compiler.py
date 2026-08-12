"""Provider-neutral Continuity compilation for Phase 19.4.6."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectNotOpenError, ProjectService


class ContinuityCompilerError(RuntimeError):
    """Raised when production Continuity authority cannot be processed safely."""


class ContinuityCompilationStatus(StrEnum):
    """Governance state for reviewed production Continuity authority."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class ContinuityCompilationDraft:
    """Reviewed provider-neutral Continuity authority for one Production Package."""

    shot_id: str
    source_package_id: str
    dependency_fingerprint: str
    previous_shot_id: str = ""
    continuity: dict[str, Any] | None = None
    production_notes: str = ""
    status: ContinuityCompilationStatus = ContinuityCompilationStatus.DRAFT

    def continuity_value(self) -> dict[str, Any]:
        """Return the detached continuity payload."""
        return dict(self.continuity or {})


class ContinuityCompilerService:
    """Compile inherited Shot state into canonical production Continuity authority."""

    FILE_NAME = "continuity_compilation.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService, packages: ProductionPackageService) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[ContinuityCompilationDraft, ...]:
        path = self.draft_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            drafts = tuple(self._from_dict(item) for item in raw.get("continuity_compilation", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ContinuityCompilerError(f"Unable to load Continuity Compiler drafts: {exc}") from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> ContinuityCompilationDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> ContinuityCompilationDraft:
        """Derive continuity from governed current and previous Shot state without invention."""
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise ContinuityCompilerError(f"Continuity compilation already exists for {normalized}")
        package = self.packages.current_package(normalized)
        if package is None:
            package = self.packages.materialize(normalized)
        previous = self._previous_package(normalized)
        draft = ContinuityCompilationDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            dependency_fingerprint=self._dependency_fingerprint(package, previous),
            previous_shot_id=previous.shot_id if previous is not None else "",
            continuity=self._build_continuity(package, previous),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> ContinuityCompilationDraft:
        """Refresh inherited state while preserving explicit human review notes."""
        current = self._require_draft(shot_id)
        if current.status is ContinuityCompilationStatus.READY:
            raise ContinuityCompilerError(
                "Ready Continuity compilation must return to Draft before refreshing its source"
            )
        package = self.packages.require_current_package(current.shot_id)
        previous = self._previous_package(current.shot_id)
        dependency = self._dependency_fingerprint(package, previous)
        if current.dependency_fingerprint == dependency:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            dependency_fingerprint=dependency,
            previous_shot_id=previous.shot_id if previous is not None else "",
            continuity=self._build_continuity(package, previous),
        )
        self._replace(updated)
        return updated

    def save_notes(self, shot_id: str, production_notes: str) -> ContinuityCompilationDraft:
        current = self._require_draft(shot_id)
        if current.status is ContinuityCompilationStatus.READY:
            raise ContinuityCompilerError(
                "Ready Continuity compilation must return to Draft before editing"
            )
        if not self.is_current(current):
            raise ContinuityCompilerError(
                "Continuity compilation is stale against current inherited production state"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> ContinuityCompilationDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise ContinuityCompilerError(
                "Continuity compilation is stale against current inherited production state"
            )
        continuity = current.continuity_value()
        self._validate_continuity(continuity)
        ready = replace(current, status=ContinuityCompilationStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> ContinuityCompilationDraft:
        current = self._require_draft(shot_id)
        draft = replace(current, status=ContinuityCompilationStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: ContinuityCompilationDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        if package is None:
            return False
        previous = self._previous_package(draft.shot_id)
        return draft.dependency_fingerprint == self._dependency_fingerprint(package, previous)

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not ContinuityCompilationStatus.READY:
            raise ContinuityCompilerError("Only Ready Continuity compilation may be compiled")
        if not self.is_current(draft):
            raise ContinuityCompilerError("Continuity compilation is stale and cannot be compiled")
        continuity = draft.continuity_value()
        self._validate_continuity(continuity)
        compiled = self._compile_continuity(continuity)
        return self.packages.derive_continuity(
            draft.shot_id,
            compiled,
            production_notes=draft.production_notes,
        )

    @classmethod
    def _build_continuity(
        cls,
        package: ProductionPackage,
        previous: ProductionPackage | None,
    ) -> dict[str, Any]:
        current_opening = cls._action_value(package, "opening_state") or str(
            package.shot.get("continuity_in", "")
        ).strip()
        current_closing = cls._action_value(package, "closing_state") or str(
            package.shot.get("continuity_out", "")
        ).strip()
        previous_closing = cls._previous_closing(previous)
        effective_opening = current_opening or previous_closing
        conflicts: list[str] = []
        if current_opening and previous_closing and current_opening != previous_closing:
            conflicts.append(
                "Current opening state differs from the previous Shot closing state; user review required."
            )

        current_assets = cls._asset_ids(package)
        previous_assets = cls._asset_ids(previous) if previous is not None else ()
        current_screen_direction = cls._section_value(package.camera, "screen_direction")
        previous_screen_direction = (
            cls._section_value(previous.camera, "screen_direction") if previous is not None else ""
        )
        current_lighting_notes = cls._section_value(package.lighting, "continuity_notes")
        previous_lighting_notes = (
            cls._section_value(previous.lighting, "continuity_notes") if previous is not None else ""
        )

        return {
            "current_shot_id": package.shot_id,
            "previous_shot_id": previous.shot_id if previous is not None else "",
            "current_opening_state": current_opening,
            "previous_closing_state": previous_closing,
            "effective_opening_state": effective_opening,
            "current_closing_state": current_closing,
            "current_asset_ids": list(current_assets),
            "previous_asset_ids": list(previous_assets),
            "current_screen_direction": current_screen_direction,
            "previous_screen_direction": previous_screen_direction,
            "current_lighting_continuity": current_lighting_notes,
            "previous_lighting_continuity": previous_lighting_notes,
            "environment": cls._detached(package.environment),
            "continuity_conflicts": conflicts,
            "inheritance_mode": "previous-shot-closing-state" if previous is not None else "series-entry",
        }

    @classmethod
    def _compile_continuity(cls, continuity: dict[str, Any]) -> dict[str, Any]:
        governed = cls._detached(continuity)
        return {
            "governed": governed,
            "production": {
                "previous_shot_id": governed.get("previous_shot_id", ""),
                "opening_state": governed.get("effective_opening_state", ""),
                "closing_state": governed.get("current_closing_state", ""),
                "asset_ids": governed.get("current_asset_ids", []),
                "previous_asset_ids": governed.get("previous_asset_ids", []),
                "screen_direction": governed.get("current_screen_direction", ""),
                "previous_screen_direction": governed.get("previous_screen_direction", ""),
                "lighting_continuity": governed.get("current_lighting_continuity", ""),
                "previous_lighting_continuity": governed.get(
                    "previous_lighting_continuity", ""
                ),
                "environment": governed.get("environment", {}),
                "conflicts": governed.get("continuity_conflicts", []),
                "inheritance_mode": governed.get("inheritance_mode", ""),
                "provider_neutral": True,
            },
        }

    @staticmethod
    def _validate_continuity(continuity: dict[str, Any]) -> None:
        if not str(continuity.get("current_shot_id", "")).strip():
            raise ContinuityCompilerError("Continuity authority is missing the current Shot identity")
        if "effective_opening_state" not in continuity or "current_closing_state" not in continuity:
            raise ContinuityCompilerError("Continuity authority is incomplete")

    def _previous_package(self, shot_id: str) -> ProductionPackage | None:
        planning = self.packages.planning
        current_ids = sorted(
            {
                item.shot_id
                for item in planning.list_packages()
                if planning.is_current(item)
            }
        )
        normalized = shot_id.strip().upper()
        if normalized not in current_ids:
            return None
        index = current_ids.index(normalized)
        if index == 0:
            return None
        return self.packages.current_package(current_ids[index - 1])

    @classmethod
    def _dependency_fingerprint(
        cls,
        package: ProductionPackage,
        previous: ProductionPackage | None,
    ) -> str:
        payload: dict[str, Any] = {
            "current": cls._dependency_payload(package),
            "previous": cls._dependency_payload(previous) if previous is not None else None,
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _dependency_payload(cls, package: ProductionPackage) -> dict[str, Any]:
        return {
            "shot_id": package.shot_id,
            "shot": cls._detached(package.shot),
            "assets": cls._detached_list(package.assets),
            "camera": cls._detached(package.camera),
            "lighting": cls._detached(package.lighting),
            "environment": cls._detached(package.environment),
            "action_performance": cls._detached(package.action_performance),
        }

    @classmethod
    def _previous_closing(cls, package: ProductionPackage | None) -> str:
        if package is None:
            return ""
        production = package.continuity.get("production")
        if isinstance(production, dict):
            value = str(production.get("closing_state", "")).strip()
            if value:
                return value
        return cls._action_value(package, "closing_state") or str(
            package.shot.get("continuity_out", "")
        ).strip()

    @staticmethod
    def _section_value(section: dict[str, Any], key: str) -> str:
        production = section.get("production")
        if isinstance(production, dict) and production.get(key) not in (None, ""):
            return str(production.get(key, "")).strip()
        governed = section.get("governed")
        if isinstance(governed, dict) and governed.get(key) not in (None, ""):
            return str(governed.get(key, "")).strip()
        return str(section.get(key, "")).strip()

    @staticmethod
    def _action_value(package: ProductionPackage, key: str) -> str:
        return str(package.action_performance.get(key, "")).strip()

    @staticmethod
    def _asset_ids(package: ProductionPackage) -> tuple[str, ...]:
        values: list[str] = []
        for item in package.assets:
            asset_id = ""
            production = item.get("production")
            resolution = item.get("resolution")
            binding = item.get("binding")
            if isinstance(production, dict):
                asset_id = str(production.get("asset_id", "")).strip()
            if not asset_id and isinstance(resolution, dict):
                asset_id = str(resolution.get("asset_id", "")).strip()
            if not asset_id and isinstance(binding, dict):
                asset_id = str(binding.get("asset_id", "")).strip()
            if asset_id and asset_id not in values:
                values.append(asset_id)
        return tuple(values)

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise ContinuityCompilerError("Continuity Compiler value is not a JSON object")
        return dict(decoded)

    @staticmethod
    def _detached_list(value: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
        decoded = json.loads(json.dumps(list(value), sort_keys=True, default=str))
        if not isinstance(decoded, list) or not all(isinstance(item, dict) for item in decoded):
            raise ContinuityCompilerError("Continuity Compiler asset value is not an object list")
        return [dict(item) for item in decoded]

    def _require_draft(self, shot_id: str) -> ContinuityCompilationDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise ContinuityCompilerError(
                f"No Continuity compilation exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: ContinuityCompilationDraft) -> None:
        drafts = tuple(
            updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
        )
        self._write(drafts)

    def _write(self, drafts: tuple[ContinuityCompilationDraft, ...]) -> None:
        path = self.draft_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "continuity_compilation": [self._to_dict(item) for item in drafts],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _to_dict(draft: ContinuityCompilationDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> ContinuityCompilationDraft:
        continuity = data.get("continuity", {})
        if not isinstance(continuity, dict):
            raise ContinuityCompilerError("Continuity Compiler draft payload is invalid")
        return ContinuityCompilationDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            dependency_fingerprint=str(data["dependency_fingerprint"]),
            previous_shot_id=str(data.get("previous_shot_id", "")),
            continuity=dict(continuity),
            production_notes=str(data.get("production_notes", "")),
            status=ContinuityCompilationStatus(str(data.get("status", "draft"))),
        )
