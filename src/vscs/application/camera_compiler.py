"""Provider-neutral Camera compilation for Phase 19.4.4."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectNotOpenError, ProjectService


class CameraCompilerError(RuntimeError):
    """Raised when production Camera authority cannot be processed safely."""


class CameraCompilationStatus(StrEnum):
    """Governance state for reviewed production Camera authority."""

    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class CameraCompilationDraft:
    """Reviewed provider-neutral Camera authority for one Production Package."""

    shot_id: str
    source_package_id: str
    source_fingerprint: str
    camera: dict[str, Any]
    production_notes: str = ""
    status: CameraCompilationStatus = CameraCompilationStatus.DRAFT


class CameraCompilerService:
    """Compile governed Camera planning into canonical production Camera intent."""

    FILE_NAME = "camera_compilation.json"
    SCHEMA_VERSION = "1.0"

    def __init__(self, projects: ProjectService, packages: ProductionPackageService) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[CameraCompilationDraft, ...]:
        path = self.draft_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            drafts = tuple(self._from_dict(item) for item in raw.get("camera_compilation", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise CameraCompilerError(f"Unable to load Camera Compiler drafts: {exc}") from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> CameraCompilationDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> CameraCompilationDraft:
        """Seed exactly from governed Camera planning; never invent Camera intent."""
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise CameraCompilerError(f"Camera compilation already exists for {normalized}")
        package = self.packages.current_package(normalized)
        if package is None:
            package = self.packages.materialize(normalized)
        if not package.camera:
            raise CameraCompilerError("Current Production Package has no governed Camera plan")
        draft = CameraCompilationDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            camera=self._detached(package.camera),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> CameraCompilationDraft:
        """Refresh stale Camera authority while preserving human production notes."""
        current = self._require_draft(shot_id)
        if current.status is CameraCompilationStatus.READY:
            raise CameraCompilerError(
                "Ready Camera compilation must return to Draft before refreshing its source"
            )
        package = self.packages.require_current_package(current.shot_id)
        if not package.camera:
            raise CameraCompilerError("Current Production Package has no governed Camera plan")
        if current.source_fingerprint == package.source_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            source_fingerprint=package.source_fingerprint,
            camera=self._detached(package.camera),
        )
        self._replace(updated)
        return updated

    def save_notes(self, shot_id: str, production_notes: str) -> CameraCompilationDraft:
        current = self._require_draft(shot_id)
        if current.status is CameraCompilationStatus.READY:
            raise CameraCompilerError("Ready Camera compilation must return to Draft before editing")
        if not self.is_current(current):
            raise CameraCompilerError(
                "Camera compilation is stale against the current Production Package"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> CameraCompilationDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise CameraCompilerError(
                "Camera compilation is stale against the current Production Package"
            )
        self._validate_camera(current.camera)
        ready = replace(current, status=CameraCompilationStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> CameraCompilationDraft:
        current = self._require_draft(shot_id)
        draft = replace(current, status=CameraCompilationStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: CameraCompilationDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        return package is not None and package.source_fingerprint == draft.source_fingerprint

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not CameraCompilationStatus.READY:
            raise CameraCompilerError("Only Ready Camera compilation may be compiled")
        if not self.is_current(draft):
            raise CameraCompilerError("Camera compilation is stale and cannot be compiled")
        self._validate_camera(draft.camera)
        compiled = self._compile_camera(draft.camera)
        return self.packages.derive_camera(
            draft.shot_id,
            compiled,
            production_notes=draft.production_notes,
        )

    @classmethod
    def _compile_camera(cls, camera: dict[str, Any]) -> dict[str, Any]:
        governed = cls._detached(camera)
        return {
            "governed": governed,
            "production": {
                "shot_size": governed.get("shot_size"),
                "angle": governed.get("angle"),
                "movement": governed.get("movement"),
                "lens_family": governed.get("lens_family"),
                "focal_length_mm": governed.get("focal_length_mm"),
                "camera_height_m": governed.get("camera_height_m"),
                "screen_direction": governed.get("screen_direction"),
                "composition": governed.get("composition"),
                "focus_strategy": governed.get("focus_strategy"),
                "movement_notes": governed.get("movement_notes"),
                "continuity_notes": governed.get("continuity_notes"),
                "camera_constraints": governed.get("camera_constraints", []),
                "camera_profile_asset_id": governed.get("camera_profile_asset_id", ""),
                "provider_neutral": True,
            },
        }

    @staticmethod
    def _validate_camera(camera: dict[str, Any]) -> None:
        required = (
            "shot_size",
            "angle",
            "movement",
            "lens_family",
            "focal_length_mm",
            "camera_height_m",
            "screen_direction",
            "composition",
            "focus_strategy",
        )
        missing = [key for key in required if camera.get(key) in (None, "")]
        if missing:
            raise CameraCompilerError(
                "Governed Camera plan is incomplete: " + ", ".join(sorted(missing))
            )

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise CameraCompilerError("Camera Compiler value is not a JSON object")
        return dict(decoded)

    def _require_draft(self, shot_id: str) -> CameraCompilationDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise CameraCompilerError(
                f"No Camera compilation exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: CameraCompilationDraft) -> None:
        drafts = tuple(
            updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
        )
        self._write(drafts)

    def _write(self, drafts: tuple[CameraCompilationDraft, ...]) -> None:
        path = self.draft_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "camera_compilation": [self._to_dict(item) for item in drafts],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _to_dict(draft: CameraCompilationDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> CameraCompilationDraft:
        camera = data.get("camera")
        if not isinstance(camera, dict):
            raise CameraCompilerError("Camera Compiler draft Camera plan is invalid")
        return CameraCompilationDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            source_fingerprint=str(data["source_fingerprint"]),
            camera=dict(camera),
            production_notes=str(data.get("production_notes", "")),
            status=CameraCompilationStatus(str(data.get("status", "draft"))),
        )
