"""Canonical renderer-neutral Production Package foundation for Phase 19.4."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from vscs.application.projects import ProjectNotOpenError, ProjectService
from vscs.application.story.planning_integration import (
    GovernedPlanningIntegrationService,
    IntegratedPlanningPackage,
)


class ProductionPackageError(RuntimeError):
    """Raised when canonical production intelligence cannot be materialized safely."""


class ProductionPackageStatus(StrEnum):
    """Lifecycle state of the canonical Phase 19.4 package."""

    FOUNDATION = "foundation"
    COMPILING = "compiling"
    STALE = "stale"


@dataclass(frozen=True, slots=True)
class ProductionPackageProvenance:
    """Trace the package back to the immutable approved planning authority."""

    integrated_package_id: str
    integrated_package_fingerprint: str
    planning_review_id: str
    planning_review_fingerprint: str


@dataclass(frozen=True, slots=True)
class ProductionPackage:
    """Canonical source of production intent from which specialist compilers build."""

    package_id: str
    shot_id: str
    schema_version: str
    source_fingerprint: str
    package_fingerprint: str
    provenance: ProductionPackageProvenance
    story_context: dict[str, Any]
    shot: dict[str, Any]
    assets: tuple[dict[str, Any], ...]
    camera: dict[str, Any]
    lighting: dict[str, Any]
    environment: dict[str, Any]
    action_performance: dict[str, Any]
    continuity: dict[str, Any]
    style: dict[str, Any]
    dialogue: tuple[dict[str, Any], ...]
    effects: tuple[dict[str, Any], ...]
    references: tuple[dict[str, Any], ...]
    universal_description: dict[str, Any]
    provider_outputs: dict[str, Any]
    validation: dict[str, Any]
    status: ProductionPackageStatus = ProductionPackageStatus.FOUNDATION


class ProductionPackageService:
    """Materialize and persist canonical Phase 19.4 packages without provider leakage."""

    FILE_NAME = "production_packages.json"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        planning: GovernedPlanningIntegrationService,
    ) -> None:
        self.projects = projects
        self.planning = planning

    @property
    def package_file(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory / "production" / self.FILE_NAME

    def list_packages(self, *, shot_id: str | None = None) -> tuple[ProductionPackage, ...]:
        path = self.package_file
        if not path.is_file():
            return ()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            packages = tuple(self._from_dict(item) for item in raw.get("production_packages", []))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ProductionPackageError(f"Unable to load Production Packages: {exc}") from exc
        if shot_id is not None:
            normalized = shot_id.strip().upper()
            packages = tuple(item for item in packages if item.shot_id == normalized)
        return packages

    def materialize(self, shot_id: str) -> ProductionPackage:
        """Create the canonical foundation from the current approved planning package."""
        integrated = self.planning.require_current_package(shot_id)
        source_fingerprint = integrated.package_fingerprint
        existing = next(
            (
                package
                for package in reversed(self.list_packages(shot_id=integrated.shot_id))
                if package.source_fingerprint == source_fingerprint
            ),
            None,
        )
        if existing is not None:
            return existing

        package = self._build(integrated)
        self._write((*self.list_packages(), package))
        return package

    def current_package(self, shot_id: str) -> ProductionPackage | None:
        integrated = self.planning.current_package(shot_id)
        if integrated is None:
            return None
        return next(
            (
                package
                for package in reversed(self.list_packages(shot_id=integrated.shot_id))
                if package.source_fingerprint == integrated.package_fingerprint
            ),
            None,
        )

    def require_current_package(self, shot_id: str) -> ProductionPackage:
        package = self.current_package(shot_id)
        if package is None:
            raise ProductionPackageError(
                f"No current Production Package exists for {shot_id.strip().upper()}"
            )
        return package

    def is_current(self, package: ProductionPackage) -> bool:
        current = self.current_package(package.shot_id)
        return current is not None and current.package_id == package.package_id

    def derive_action_performance(
        self,
        shot_id: str,
        compiled: dict[str, Any],
    ) -> ProductionPackage:
        """Append a deterministic package revision containing Action & Performance output."""
        current = self.require_current_package(shot_id)
        if current.action_performance == compiled:
            return current
        data = asdict(current)
        data.pop("package_id", None)
        data.pop("package_fingerprint", None)
        data["action_performance"] = dict(compiled)
        validation = dict(current.validation)
        validation["action_performance_complete"] = True
        data["validation"] = validation
        data["status"] = ProductionPackageStatus.COMPILING.value
        return self._append_derived(current, data)

    def derive_assets(
        self,
        shot_id: str,
        compiled: tuple[dict[str, Any], ...],
        *,
        production_notes: str = "",
    ) -> ProductionPackage:
        """Append a deterministic package revision containing reviewed Asset authority."""
        current = self.require_current_package(shot_id)
        if current.assets == compiled and current.validation.get("assets_complete") is True:
            return current
        data = asdict(current)
        data.pop("package_id", None)
        data.pop("package_fingerprint", None)
        data["assets"] = [dict(item) for item in compiled]
        data["references"] = self._reference_index([dict(item) for item in compiled])
        validation = dict(current.validation)
        validation["assets_complete"] = True
        if production_notes.strip():
            validation["asset_review_notes"] = production_notes.strip()
        else:
            validation.pop("asset_review_notes", None)
        data["validation"] = validation
        data["status"] = ProductionPackageStatus.COMPILING.value
        return self._append_derived(current, data)

    def _append_derived(
        self,
        current: ProductionPackage,
        data: dict[str, Any],
    ) -> ProductionPackage:
        canonical = json.dumps(data, sort_keys=True, default=str, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        package_id = f"PP-{current.shot_id}-{fingerprint[:12].upper()}"
        existing = next(
            (
                package
                for package in reversed(self.list_packages(shot_id=current.shot_id))
                if package.package_fingerprint == fingerprint
            ),
            None,
        )
        if existing is not None:
            return existing
        data["package_id"] = package_id
        data["package_fingerprint"] = fingerprint
        derived = self._from_dict(data)
        self._write((*self.list_packages(), derived))
        return derived

    def _build(self, integrated: IntegratedPlanningPackage) -> ProductionPackage:
        source = integrated.payload()
        shot = self._object(source, "shot")
        assets = self._objects(source, "assets")
        camera = self._object(source, "camera")
        lighting = self._object(source, "lighting")
        environment = self._object(source, "environment")

        foundation: dict[str, Any] = {
            "schema_version": self.SCHEMA_VERSION,
            "shot_id": integrated.shot_id,
            "source_fingerprint": integrated.package_fingerprint,
            "provenance": {
                "integrated_package_id": integrated.package_id,
                "integrated_package_fingerprint": integrated.package_fingerprint,
                "planning_review_id": integrated.review_id,
                "planning_review_fingerprint": integrated.review_fingerprint,
            },
            "story_context": {"shot_id": integrated.shot_id},
            "shot": shot,
            "assets": assets,
            "camera": camera,
            "lighting": lighting,
            "environment": environment,
            "action_performance": {},
            "continuity": {},
            "style": {},
            "dialogue": [],
            "effects": [],
            "references": self._reference_index(assets),
            "universal_description": {},
            "provider_outputs": {},
            "validation": {
                "foundation_complete": True,
                "source_current_at_materialization": True,
                "specialist_compilation_complete": False,
                "provider_neutral": True,
            },
            "status": ProductionPackageStatus.FOUNDATION.value,
        }
        canonical = json.dumps(foundation, sort_keys=True, default=str, separators=(",", ":"))
        fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        package_id = f"PP-{integrated.shot_id}-{fingerprint[:12].upper()}"
        provenance = ProductionPackageProvenance(**foundation["provenance"])
        return ProductionPackage(
            package_id=package_id,
            shot_id=integrated.shot_id,
            schema_version=self.SCHEMA_VERSION,
            source_fingerprint=integrated.package_fingerprint,
            package_fingerprint=fingerprint,
            provenance=provenance,
            story_context=foundation["story_context"],
            shot=shot,
            assets=tuple(assets),
            camera=camera,
            lighting=lighting,
            environment=environment,
            action_performance={},
            continuity={},
            style={},
            dialogue=(),
            effects=(),
            references=tuple(foundation["references"]),
            universal_description={},
            provider_outputs={},
            validation=foundation["validation"],
        )

    @staticmethod
    def _object(source: dict[str, Any], key: str) -> dict[str, Any]:
        value = source.get(key)
        if not isinstance(value, dict):
            raise ProductionPackageError(f"Integrated planning field '{key}' is not an object")
        return dict(value)

    @staticmethod
    def _objects(source: dict[str, Any], key: str) -> list[dict[str, Any]]:
        value = source.get(key)
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ProductionPackageError(f"Integrated planning field '{key}' is not an object list")
        return [dict(item) for item in value]

    @staticmethod
    def _reference_index(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        for item in assets:
            resolution = item.get("resolution")
            if not isinstance(resolution, dict):
                continue
            reference = resolution.get("canonical_reference")
            if reference:
                references.append(
                    {
                        "asset_id": resolution.get("asset_id"),
                        "canonical_reference": reference,
                    }
                )
        return references

    def _write(self, packages: tuple[ProductionPackage, ...]) -> None:
        path = self.package_file
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "production_packages": [self._to_dict(package) for package in packages],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _to_dict(package: ProductionPackage) -> dict[str, Any]:
        data = asdict(package)
        data["status"] = package.status.value
        return data

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> ProductionPackage:
        provenance_raw = data["provenance"]
        if not isinstance(provenance_raw, dict):
            raise ProductionPackageError("Production Package provenance is invalid")
        return ProductionPackage(
            package_id=str(data["package_id"]),
            shot_id=str(data["shot_id"]),
            schema_version=str(data["schema_version"]),
            source_fingerprint=str(data["source_fingerprint"]),
            package_fingerprint=str(data["package_fingerprint"]),
            provenance=ProductionPackageProvenance(
                integrated_package_id=str(provenance_raw["integrated_package_id"]),
                integrated_package_fingerprint=str(
                    provenance_raw["integrated_package_fingerprint"]
                ),
                planning_review_id=str(provenance_raw["planning_review_id"]),
                planning_review_fingerprint=str(provenance_raw["planning_review_fingerprint"]),
            ),
            story_context=dict(data.get("story_context", {})),
            shot=dict(data["shot"]),
            assets=tuple(dict(item) for item in data.get("assets", [])),
            camera=dict(data["camera"]),
            lighting=dict(data["lighting"]),
            environment=dict(data["environment"]),
            action_performance=dict(data.get("action_performance", {})),
            continuity=dict(data.get("continuity", {})),
            style=dict(data.get("style", {})),
            dialogue=tuple(dict(item) for item in data.get("dialogue", [])),
            effects=tuple(dict(item) for item in data.get("effects", [])),
            references=tuple(dict(item) for item in data.get("references", [])),
            universal_description=dict(data.get("universal_description", {})),
            provider_outputs=dict(data.get("provider_outputs", {})),
            validation=dict(data.get("validation", {})),
            status=ProductionPackageStatus(str(data.get("status", "foundation"))),
        )
