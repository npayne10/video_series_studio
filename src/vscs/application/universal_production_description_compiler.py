"""Provider-neutral Universal Production Description compilation for Phase 19.4.8."""

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


class UniversalProductionDescriptionCompilerError(RuntimeError):
    """Raised when Universal Production Description authority cannot be processed safely."""


class UniversalProductionDescriptionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"


@dataclass(frozen=True, slots=True)
class UniversalProductionDescriptionDraft:
    shot_id: str
    source_package_id: str
    dependency_fingerprint: str
    description: dict[str, Any] | None = None
    production_notes: str = ""
    status: UniversalProductionDescriptionStatus = UniversalProductionDescriptionStatus.DRAFT

    def description_value(self) -> dict[str, Any]:
        return dict(self.description or {})


class UniversalProductionDescriptionCompilerService:
    """Compile all governed Shot authority into one provider-neutral production description."""

    FILE_NAME = "universal_production_description_compilation.json"
    SCHEMA_VERSION = "1.0"
    REQUIRED_UPSTREAM = (
        ("action_performance_complete", "Action & Performance"),
        ("assets_complete", "Assets"),
        ("camera_complete", "Camera"),
        ("lighting_complete", "Lighting"),
        ("continuity_complete", "Continuity"),
        ("style_complete", "Style"),
    )

    def __init__(self, projects: ProjectService, packages: ProductionPackageService) -> None:
        self.projects = projects
        self.packages = packages

    @property
    def draft_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_drafts(self) -> tuple[UniversalProductionDescriptionDraft, ...]:
        if not self.draft_file.is_file():
            return ()
        try:
            raw = json.loads(self.draft_file.read_text(encoding="utf-8"))
            drafts = tuple(
                self._from_dict(item)
                for item in raw.get("universal_production_description_compilation", [])
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise UniversalProductionDescriptionCompilerError(
                f"Unable to load Universal Production Description drafts: {exc}"
            ) from exc
        return tuple(sorted(drafts, key=lambda item: item.shot_id))

    def draft(self, shot_id: str) -> UniversalProductionDescriptionDraft | None:
        normalized = shot_id.strip().upper()
        return next((item for item in self.list_drafts() if item.shot_id == normalized), None)

    def create_from_current_package(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        normalized = shot_id.strip().upper()
        if self.draft(normalized) is not None:
            raise UniversalProductionDescriptionCompilerError(
                f"Universal Production Description compilation already exists for {normalized}"
            )
        package = self.packages.current_package(normalized) or self.packages.materialize(normalized)
        draft = UniversalProductionDescriptionDraft(
            shot_id=normalized,
            source_package_id=package.package_id,
            dependency_fingerprint=self._dependency_fingerprint(package),
            description=self._build_description(package),
        )
        self._write((*self.list_drafts(), draft))
        return draft

    def rebase_to_current_package(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Ready Universal Production Description must return to Draft before refreshing"
            )
        package = self.packages.require_current_package(current.shot_id)
        fingerprint = self._dependency_fingerprint(package)
        if fingerprint == current.dependency_fingerprint:
            return current
        updated = replace(
            current,
            source_package_id=package.package_id,
            dependency_fingerprint=fingerprint,
            description=self._build_description(package),
        )
        self._replace(updated)
        return updated

    def save_notes(
        self, shot_id: str, production_notes: str
    ) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if current.status is UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Ready Universal Production Description must return to Draft before editing"
            )
        if not self.is_current(current):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale against current production authority"
            )
        updated = replace(current, production_notes=production_notes.strip())
        self._replace(updated)
        return updated

    def mark_ready(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        current = self._require_draft(shot_id)
        if not self.is_current(current):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale against current production authority"
            )
        self._require_upstream_ready(current.shot_id)
        self._validate(current.description_value())
        ready = replace(current, status=UniversalProductionDescriptionStatus.READY)
        self._replace(ready)
        self.compile(ready.shot_id)
        return ready

    def return_to_draft(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        draft = replace(
            self._require_draft(shot_id), status=UniversalProductionDescriptionStatus.DRAFT
        )
        self._replace(draft)
        return draft

    def is_current(self, draft: UniversalProductionDescriptionDraft) -> bool:
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
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            raise UniversalProductionDescriptionCompilerError(
                "Only Ready Universal Production Description may be compiled"
            )
        if not self.is_current(draft):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is stale and cannot be compiled"
            )
        self._require_upstream_ready(draft.shot_id)
        description = draft.description_value()
        self._validate(description)
        return self._derive(
            draft.shot_id,
            self._compile_description(description),
            production_notes=draft.production_notes,
        )

    def _require_upstream_ready(self, shot_id: str) -> None:
        missing = self.missing_prerequisites(shot_id)
        if missing:
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description cannot be finalized until upstream authority is Ready: "
                + ", ".join(missing)
            )

    def _derive(
        self, shot_id: str, compiled: dict[str, Any], *, production_notes: str = ""
    ) -> ProductionPackage:
        current = self.packages.require_current_package(shot_id)
        if (
            current.universal_description == compiled
            and current.validation.get("universal_description_complete") is True
        ):
            return current
        data = asdict(current)
        data.pop("package_id", None)
        data.pop("package_fingerprint", None)
        data["universal_description"] = dict(compiled)
        validation = dict(current.validation)
        validation["universal_description_complete"] = True
        if production_notes.strip():
            validation["universal_description_review_notes"] = production_notes.strip()
        else:
            validation.pop("universal_description_review_notes", None)
        data["validation"] = validation
        data["status"] = ProductionPackageStatus.COMPILING.value
        append_derived: Any = self.packages._append_derived
        derived: ProductionPackage = append_derived(current, data)
        return derived

    @classmethod
    def _build_description(cls, package: ProductionPackage) -> dict[str, Any]:
        action = cls._section(package.action_performance)
        camera = cls._section(package.camera)
        lighting = cls._section(package.lighting)
        continuity = cls._section(package.continuity)
        style = cls._section(package.style)
        assets = [cls._section(item) for item in package.assets]
        description = {
            "current_shot_id": package.shot_id,
            "story_context": cls._detached(package.story_context),
            "shot": cls._detached(package.shot),
            "action_performance": action,
            "assets": assets,
            "camera": camera,
            "lighting": lighting,
            "environment": cls._detached(package.environment),
            "continuity": continuity,
            "style": style,
            "dialogue": [dict(item) for item in package.dialogue],
            "effects": [dict(item) for item in package.effects],
            "canonical_references": [dict(item) for item in package.references],
            "source_policy": "approved-production-authority-only",
            "provider_neutral": True,
        }
        description["universal_text"] = cls._universal_text(description)
        return description

    @classmethod
    def _compile_description(cls, description: dict[str, Any]) -> dict[str, Any]:
        governed = cls._detached(description)
        return {
            "governed": governed,
            "production": {
                "current_shot_id": governed.get("current_shot_id", ""),
                "universal_text": governed.get("universal_text", ""),
                "story_context": governed.get("story_context", {}),
                "shot": governed.get("shot", {}),
                "action_performance": governed.get("action_performance", {}),
                "assets": governed.get("assets", []),
                "camera": governed.get("camera", {}),
                "lighting": governed.get("lighting", {}),
                "environment": governed.get("environment", {}),
                "continuity": governed.get("continuity", {}),
                "style": governed.get("style", {}),
                "dialogue": governed.get("dialogue", []),
                "effects": governed.get("effects", []),
                "canonical_references": governed.get("canonical_references", []),
                "source_policy": governed.get("source_policy", ""),
                "provider_neutral": True,
            },
        }

    @staticmethod
    def _validate(value: dict[str, Any]) -> None:
        if not str(value.get("current_shot_id", "")).strip():
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description is missing the current Shot identity"
            )
        if value.get("provider_neutral") is not True:
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description must remain provider-neutral"
            )
        if not str(value.get("universal_text", "")).strip():
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description has no governed production content"
            )

    @classmethod
    def _dependency_fingerprint(cls, package: ProductionPackage) -> str:
        payload = {
            "schema_version": cls.SCHEMA_VERSION,
            "story_context": cls._detached(package.story_context),
            "shot": cls._detached(package.shot),
            "action_performance": cls._detached(package.action_performance),
            "assets": [cls._detached(item) for item in package.assets],
            "camera": cls._detached(package.camera),
            "lighting": cls._detached(package.lighting),
            "environment": cls._detached(package.environment),
            "continuity": cls._detached(package.continuity),
            "style": cls._detached(package.style),
            "dialogue": [dict(item) for item in package.dialogue],
            "effects": [dict(item) for item in package.effects],
            "references": [dict(item) for item in package.references],
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _universal_text(cls, description: dict[str, Any]) -> str:
        sections: list[str] = []
        for label, key in (
            ("SHOT", "shot"),
            ("ACTION & PERFORMANCE", "action_performance"),
            ("ASSETS", "assets"),
            ("CAMERA", "camera"),
            ("LIGHTING", "lighting"),
            ("ENVIRONMENT", "environment"),
            ("CONTINUITY", "continuity"),
            ("STYLE", "style"),
            ("DIALOGUE", "dialogue"),
            ("EFFECTS", "effects"),
            ("CANONICAL REFERENCES", "canonical_references"),
        ):
            value = description.get(key)
            if value in (None, "", {}, []):
                continue
            rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            sections.append(f"{label}: {rendered}")
        return "\n".join(sections)

    @staticmethod
    def _section(value: dict[str, Any]) -> dict[str, Any]:
        for name in ("production", "governed"):
            nested = value.get(name)
            if isinstance(nested, dict):
                return dict(nested)
        return dict(value)

    @staticmethod
    def _detached(value: dict[str, Any]) -> dict[str, Any]:
        decoded = json.loads(json.dumps(value, sort_keys=True, default=str))
        if not isinstance(decoded, dict):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description value is not a JSON object"
            )
        return dict(decoded)

    def _require_draft(self, shot_id: str) -> UniversalProductionDescriptionDraft:
        draft = self.draft(shot_id)
        if draft is None:
            raise UniversalProductionDescriptionCompilerError(
                f"No Universal Production Description exists for {shot_id.strip().upper()}"
            )
        return draft

    def _replace(self, updated: UniversalProductionDescriptionDraft) -> None:
        self._write(
            tuple(updated if item.shot_id == updated.shot_id else item for item in self.list_drafts())
        )

    def _write(self, drafts: tuple[UniversalProductionDescriptionDraft, ...]) -> None:
        self.draft_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "universal_production_description_compilation": [
                self._to_dict(item) for item in drafts
            ],
        }
        temporary = self.draft_file.with_suffix(self.draft_file.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.draft_file)

    @staticmethod
    def _to_dict(draft: UniversalProductionDescriptionDraft) -> dict[str, Any]:
        data = asdict(draft)
        data["status"] = draft.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> UniversalProductionDescriptionDraft:
        description = data.get("description", {})
        if not isinstance(description, dict):
            raise UniversalProductionDescriptionCompilerError(
                "Universal Production Description draft payload is invalid"
            )
        return UniversalProductionDescriptionDraft(
            shot_id=str(data["shot_id"]),
            source_package_id=str(data["source_package_id"]),
            dependency_fingerprint=str(data["dependency_fingerprint"]),
            description=dict(description),
            production_notes=str(data.get("production_notes", "")),
            status=UniversalProductionDescriptionStatus(str(data.get("status", "draft"))),
        )
