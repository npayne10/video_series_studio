"""Provider-neutral Style compilation for Phase 19.4.7."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageService,
    ProductionPackageStatus,
)
from vscs.application.projects import ProjectNotOpenError, ProjectService


class StyleCompilerError(RuntimeError):
    """Raised when production Style authority cannot be processed safely."""


class StyleCompilationStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class StyleCompilationDraft:
    shot_id: str
    source_package_id: str
    dependency_fingerprint: str
    style: dict[str, Any] | None = None
    production_notes: str = ""
    status: StyleCompilationStatus = StyleCompilationStatus.DRAFT

    def style_value(self) -> dict[str, Any]:
        return dict(self.style or {})


class StyleCompilerService:
    """Compile governed production choices into canonical provider-neutral Style authority."""

    FILE_NAME = "style_compilation.json"
    SCHEMA_VERSION = "1.0"
    REQUIRED_UPSTREAM = (
        ("assets_complete", "Assets"),
        ("camera_complete", "Camera"),
        ("lighting_complete", "Lighting"),
        ("continuity_complete", "Continuity"),
    )

    def __init__(self, projects: ProjectService, packages: ProductionPackageService) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[StyleCompilationDraft, ...]:
        if not self.draft_file.is_file():
            return ()
        try:
            raw = json.loads(self.draft_file.read_text(encoding="utf-8"))
            drafts = tuple(self._from_dict(item) for item in raw.get("style_compilation", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise StyleCompilerError(f"Unable to load Style Compiler drafts: {exc}") from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> StyleCompilationDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> StyleCompilationDraft:
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise StyleCompilerError(f"Style compilation already exists for {normalized}")
        package = self.packages.current_package(normalized) or self.packages.materialize(normalized)
        draft = StyleCompilationDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            dependency_fingerprint=self._dependency_fingerprint(package),
            style=self._build_style(package),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> StyleCompilationDraft:
        current = self._require_draft(shot_id)
        if current.status is StyleCompilationStatus.READY:
            raise StyleCompilerError(
                "Ready Style compilation must return to Draft before refreshing its source"
            )
        package = self.packages.require_current_package(current.shot_id)
        fingerprint = self._dependency_fingerprint(package)
        if fingerprint == current.dependency_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            dependency_fingerprint=fingerprint,
            style=self._build_style(package),
        )
        self._replace(updated)
        return updated

    def save_notes(self, shot_id: str, production_notes: str) -> StyleCompilationDraft:
        current = self._require_draft(shot_id)
        if current.status is StyleCompilationStatus.READY:
            raise StyleCompilerError("Ready Style compilation must return to Draft before editing")
        if not self.is_current(current):
            raise StyleCompilerError(
                "Style compilation is stale against current production authority"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> StyleCompilationDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise StyleCompilerError(
                "Style compilation is stale against current production authority"
            )
        self._require_upstream_ready(current.shot_id)
        self._validate(current.style_value())
        ready = replace(current, status=StyleCompilationStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> StyleCompilationDraft:
        draft = replace(self._require_draft(shot_id), status=StyleCompilationStatus.DRAFT)
        self._replace(draft)
        return draft

    def is_current(self, draft: StyleCompilationDraft) -> bool:
        package = self.packages.current_package(draft.shot_id)
        return package is not None and draft.dependency_fingerprint == self._dependency_fingerprint(
            package
        )

    def missing_prerequisites(self, shot_id: str) -> tuple[str, ...]:
        package = self.packages.current_package(shot_id.strip().upper())
        if package is None:
            return tuple(label for _key, label in self.REQUIRED_UPSTREAM)
        return tuple(
            label
            for key, label in self.REQUIRED_UPSTREAM
            if package.validation.get(key) is not True
        )

    def compile(self, shot_id: str) -> ProductionPackage:
        draft = self._require_draft(shot_id)
        if draft.status is not StyleCompilationStatus.READY:
            raise StyleCompilerError("Only Ready Style compilation may be compiled")
        if not self.is_current(draft):
            raise StyleCompilerError("Style compilation is stale and cannot be compiled")
        self._require_upstream_ready(draft.shot_id)
        style = draft.style_value()
        self._validate(style)
        return self._derive(
            draft.shot_id,
            self._compile_style(style),
            production_notes=draft.production_notes,
        )

    def _require_upstream_ready(self, shot_id: str) -> None:
        missing = self.missing_prerequisites(shot_id)
        if missing:
            raise StyleCompilerError(
                "Style cannot be finalized until upstream compiler authority is Ready: "
                + ", ".join(missing)
            )

    def _derive(
        self, shot_id: str, compiled: dict[str, Any], *, production_notes: str = ""
    ) -> ProductionPackage:
        current = self.packages.require_current_package(shot_id)
        if current.style == compiled and current.validation.get("style_complete") is True:
            return current
        data = asdict(current)
        data.pop("package_id", None)
        data.pop("package_fingerprint", None)
        data["style"] = dict(compiled)
        validation = dict(current.validation)
        validation["style_complete"] = True
        if production_notes.strip():
            validation["style_review_notes"] = production_notes.strip()
        else:
            validation.pop("style_review_notes", None)
        data["validation"] = validation
        data["status"] = ProductionPackageStatus.COMPILING.value
        append_derived: Any = self.packages._append_derived
        derived: ProductionPackage = append_derived(current, data)
        return derived

    @classmethod
    def _build_style(cls, package: ProductionPackage) -> dict[str, Any]:
        shot_style = cls._first_value(
            package.shot,
            ("style", "visual_style", "style_intent", "visual_language"),
        )
        shot_tone = cls._first_value(package.shot, ("tone", "mood", "emotional_tone"))
        camera = cls._section(package.camera)
        lighting = cls._section(package.lighting)
        continuity = cls._section(package.continuity)
        return {
            "current_shot_id": package.shot_id,
            "declared_style": shot_style,
            "declared_tone": shot_tone,
            "camera_language": cls._subset(
                camera,
                (
                    "shot_size",
                    "angle",
                    "movement",
                    "lens_family",
                    "focal_length_mm",
                    "composition",
                    "focus_strategy",
                    "movement_notes",
                    "screen_direction",
                ),
            ),
            "lighting_language": cls._subset(
                lighting,
                (
                    "lighting_intent",
                    "key_direction",
                    "key_quality",
                    "color_temperature_k",
                    "fill_level_percent",
                    "exposure_intent",
                    "source_strategy",
                    "shadow_strategy",
                    "subject_readability",
                    "separation_strategy",
                ),
            ),
            "continuity_language": cls._subset(
                continuity,
                (
                    "opening_state",
                    "closing_state",
                    "screen_direction",
                    "lighting_continuity",
                    "inheritance_mode",
                ),
            ),
            "environment_context": cls._detached(package.environment),
            "asset_ids": list(cls._asset_ids(package)),
            "canonical_references": [dict(item) for item in package.references],
            "source_policy": "governed-production-authority-only",
            "provider_neutral": True,
        }

    @classmethod
    def _compile_style(cls, style: dict[str, Any]) -> dict[str, Any]:
        governed = cls._detached(style)
        return {
            "governed": governed,
            "production": {
                "declared_style": governed.get("declared_style", ""),
                "declared_tone": governed.get("declared_tone", ""),
                "camera_language": governed.get("camera_language", {}),
                "lighting_language": governed.get("lighting_language", {}),
                "continuity_language": governed.get("continuity_language", {}),
                "environment_context": governed.get("environment_context", {}),
                "asset_ids": governed.get("asset_ids", []),
                "canonical_references": governed.get("canonical_references", []),
                "source_policy": governed.get("source_policy", ""),
                "provider_neutral": True,
            },
        }

    @staticmethod
    def _validate(value: dict[str, Any]) -> None:
        if not str(value.get("current_shot_id", "")).strip():
            raise StyleCompilerError("Style authority is missing the current Shot identity")
        if value.get("provider_neutral") is not True:
            raise StyleCompilerError("Style authority must remain provider-neutral")

    @classmethod
    def _dependency_fingerprint(cls, package: ProductionPackage) -> str:
        payload = {
            "schema_version": cls.SCHEMA_VERSION,
            "shot": cls._detached(package.shot),
            "assets": [dict(item) for item in package.assets],
            "references": [dict(item) for item in package.references],
            "camera": cls._detached(package.camera),
            "lighting": cls._detached(package.lighting),
            "environment": cls._detached(package.environment),
            "continuity": cls._detached(package.continuity),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _first_value(source: dict[str, Any], keys: tuple[str, ...]) -> str:
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return str(value).strip()
        return ""

    @staticmethod
    def _section(section: dict[str, Any]) -> dict[str, Any]:
        for name in ("production", "governed"):
            nested = section.get(name)
            if isinstance(nested, dict):
                return dict(nested)
        return dict(section)

    @staticmethod
    def _subset(source: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        return {key: source[key] for key in keys if key in source and source[key] not in (None, "")}

    @staticmethod
    def _asset_ids(package: ProductionPackage) -> tuple[str, ...]:
        values: list[str] = []
        for item in package.assets:
            asset_id = ""
            for name in ("production", "resolution", "binding"):
                nested = item.get(name)
                if isinstance(nested, dict):
                    asset_id = str(nested.get("asset_id", "")).strip()
                    if asset_id:
                        break
            if asset_id and asset_id not in values:
                values.append(asset_id)
        return tuple(values)

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise StyleCompilerError("Style Compiler value is not a JSON object")
        return dict(decoded)

    def _require_draft(self, shot_id: str) -> StyleCompilationDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise StyleCompilerError(f"No Style compilation exists for {shot_id.strip().upper()}")
        return draft

    def _replace(self, updated: StyleCompilationDraft) -> None:
        self._write(
            tuple(
                updated if item.shot_id == updated.shot_id else item for item in self.list_drafts()
            )
        )

    def _write(self, drafts: tuple[StyleCompilationDraft, ...]) -> None:
        self.draft_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "style_compilation": [self._to_dict(item) for item in drafts],
        }
        temporary = self.draft_file.with_suffix(self.draft_file.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.draft_file)

    @staticmethod
    def _to_dict(draft: StyleCompilationDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> StyleCompilationDraft:
        style = data.get("style", {})
        if not isinstance(style, dict):
            raise StyleCompilerError("Style Compiler draft payload is invalid")
        return StyleCompilationDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            dependency_fingerprint=str(data["dependency_fingerprint"]),
            style=dict(style),
            production_notes=str(data.get("production_notes", "")),
            status=StyleCompilationStatus(str(data.get("status", "draft"))),
        )
