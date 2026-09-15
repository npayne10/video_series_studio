"""Author governed ReferencePlans only from explicit provider-readiness reviews."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vscs.application.acpp.reference_roles import (
    ProviderReadyReferenceResolver,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePriority,
    ReferenceResolutionSeverity,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)
from vscs.application.governed_reference_plan_persistence import (
    GovernedReferencePlanPersistenceService,
)
from vscs.application.governed_reference_plan_source import (
    GovernedReferencePlanSourceError,
    PersistedGovernedReferencePlanSource,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.projects import ProjectNotOpenError, ProjectService


class GovernedReferenceSuitabilityError(RuntimeError):
    """Raised when explicit provider-readiness authority is absent or unsafe."""


class _EmptyReferenceCatalog:
    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        del asset_id
        return ()


class GovernedReferenceSuitabilityService:
    """Resolve explicit human-reviewed suitability facts into durable ReferencePlans.

    Canonical asset/reference approval is deliberately not sufficient here. The only
    authoring source for provider-readiness facts is the explicit per-Shot suitability
    JSON reviewed by an operator. Existing persisted plans remain reusable when no newer
    explicit suitability artifact exists.
    """

    FILE_PREFIX = "governed_reference_suitability_"
    SCHEMA_VERSION = "1.0"

    def __init__(
        self,
        projects: ProjectService,
        store: PersistedGovernedReferencePlanSource | None = None,
    ) -> None:
        self.projects = projects
        self.store = store or PersistedGovernedReferencePlanSource(projects)
        resolver = ProviderReadyReferenceResolver(_EmptyReferenceCatalog())
        self.persistence = GovernedReferencePlanPersistenceService(resolver, self.store)

    @property
    def project_directory(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory

    def suitability_file(self, shot_id: str) -> Path:
        normalized = shot_id.strip().upper()
        return self.project_directory / "production" / f"{self.FILE_PREFIX}{normalized}.json"

    def ensure_for_package(self, package: ProductionPackage) -> dict[str, Any] | None:
        """Return safe governed reference authority for the current package.

        A present suitability artifact is authoritative and is re-resolved even when a
        persisted plan already exists, allowing a newly reviewed artifact to repair a
        previously failed plan. Without an explicit artifact, only an already persisted
        passing plan may be reused. Canonical visual references alone never create
        provider-ready authority.
        """
        shot_id = package.shot_id.strip().upper()
        path = self.suitability_file(shot_id)
        if path.is_file():
            return self._resolve_explicit(package, path)

        try:
            persisted = self.store.reference_plan_for_shot(shot_id)
        except GovernedReferencePlanSourceError as exc:
            raise GovernedReferenceSuitabilityError(str(exc)) from exc
        if persisted is not None:
            self._require_passing_plan(persisted, shot_id)
            return persisted

        if package.references:
            raise GovernedReferenceSuitabilityError(
                f"Explicit provider-ready suitability authority is required for {shot_id} "
                "because canonical visual references are present, but no governed "
                "ReferencePlan has been persisted. Review provider suitability before "
                "Universal Production Description compilation."
            )
        return None

    def _resolve_explicit(
        self,
        package: ProductionPackage,
        path: Path,
    ) -> dict[str, Any]:
        try:
            raw_text = path.read_text(encoding="utf-8")
            raw = json.loads(raw_text)
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernedReferenceSuitabilityError(
                f"Unable to read explicit governed reference suitability from {path.name}: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability file {path.name} must contain a JSON object"
            )
        if str(raw.get("schema_version") or "").strip() != self.SCHEMA_VERSION:
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability file {path.name} must use schema {self.SCHEMA_VERSION}"
            )

        shot_id = package.shot_id.strip().upper()
        declared_shot = str(raw.get("shot_id") or "").strip().upper()
        if declared_shot != shot_id:
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability Shot ID mismatch: expected {shot_id}, got "
                f"{declared_shot or '<missing>'}"
            )

        target = self._target(raw.get("target"), path)
        references_raw = raw.get("references")
        if not isinstance(references_raw, list) or not references_raw:
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability file {path.name} must contain reviewed references"
            )

        allowed_asset_ids = self._package_asset_ids(package)
        supplied: list[ShotReference] = []
        requests: list[ReferenceRoleRequest] = []
        for index, item in enumerate(references_raw, start=1):
            reference = self._reference(
                item,
                index=index,
                path=path,
                allowed_asset_ids=allowed_asset_ids,
            )
            supplied.append(reference)
            requests.append(
                ReferenceRoleRequest(
                    role=reference.role,
                    priority=reference.priority,
                    asset_id=reference.asset_id,
                    preferred_reference_id=reference.reference_id,
                )
            )

        resolution = self.persistence.resolve_and_persist(
            shot_id=shot_id,
            target=target,
            requests=tuple(requests),
            supplied_references=tuple(supplied),
            provenance={
                "source": "live-explicit-suitability",
                "suitability_file": str(path),
                "suitability_file_checksum": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            },
        )
        if not resolution.passed:
            errors = [
                f"{item.code}: {item.message}"
                for item in resolution.diagnostics
                if item.severity is ReferenceResolutionSeverity.ERROR
            ]
            detail = "; ".join(errors) or "unknown provider-readiness failure"
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability review for {shot_id} did not pass: {detail}"
            )

        persisted = self.store.reference_plan_for_shot(shot_id)
        if persisted is None:
            raise GovernedReferenceSuitabilityError(
                f"Passing governed ReferencePlan for {shot_id} was not persisted"
            )
        return persisted

    def _target(self, value: object, path: Path) -> ReferenceTarget:
        if not isinstance(value, dict):
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability file {path.name} requires a target object"
            )
        width = self._positive_int(value.get("width"), "target.width")
        height = self._positive_int(value.get("height"), "target.height")
        profile_id = self._required_text(value, "profile_id", "target")
        provider_id = self._optional_text(value.get("provider_id"))
        tolerance_raw = value.get("aspect_tolerance", 0.03)
        if (
            not isinstance(tolerance_raw, int | float)
            or isinstance(tolerance_raw, bool)
            or tolerance_raw <= 0
        ):
            raise GovernedReferenceSuitabilityError(
                "Explicit suitability target.aspect_tolerance must be positive"
            )
        return ReferenceTarget(
            width=width,
            height=height,
            profile_id=profile_id,
            provider_id=provider_id,
            aspect_tolerance=float(tolerance_raw),
        )

    def _reference(
        self,
        value: object,
        *,
        index: int,
        path: Path,
        allowed_asset_ids: set[str],
    ) -> ShotReference:
        if not isinstance(value, dict):
            raise GovernedReferenceSuitabilityError(
                f"Explicit suitability reference #{index} must be a JSON object"
            )
        context = f"reference #{index}"
        reference_id = self._required_text(value, "reference_id", context)
        asset_id = self._optional_text(value.get("asset_id"))
        if asset_id is not None:
            normalized_asset = asset_id.upper()
            if normalized_asset not in allowed_asset_ids:
                raise GovernedReferenceSuitabilityError(
                    f"Reference '{reference_id}' uses asset '{asset_id}' which is not governed "
                    "by the current Production Package"
                )
            asset_id = normalized_asset

        try:
            role = ReferenceRole(self._required_text(value, "role", context))
            reference_class = ReferenceClass(self._required_text(value, "reference_class", context))
            subject_type = ReferenceSubjectType(self._required_text(value, "subject_type", context))
            priority = ReferencePriority(
                self._optional_text(value.get("priority")) or ReferencePriority.REQUIRED.value
            )
        except ValueError as exc:
            raise GovernedReferenceSuitabilityError(
                f"Reference '{reference_id}' contains an unsupported governed enum: {exc}"
            ) from exc

        source_path = self._required_text(value, "source_path", context)
        disk_path = Path(source_path).expanduser()
        if not disk_path.is_absolute():
            disk_path = self.project_directory / disk_path
        disk_path = disk_path.resolve(strict=False)
        if not disk_path.is_file():
            raise GovernedReferenceSuitabilityError(
                f"Reference '{reference_id}' source file does not exist: {disk_path}"
            )

        declared_checksum = self._required_text(value, "file_checksum", context).lower()
        actual_checksum = self._sha256_file(disk_path)
        if declared_checksum != actual_checksum:
            raise GovernedReferenceSuitabilityError(
                f"Reference '{reference_id}' file checksum does not match the explicit "
                "suitability review"
            )

        width = self._positive_int(value.get("width"), f"{context}.width")
        height = self._positive_int(value.get("height"), f"{context}.height")
        provider_ready = self._required_bool(value, "provider_ready", context)
        provider_profiles_raw = value.get("provider_profiles")
        if not isinstance(provider_profiles_raw, list | tuple):
            raise GovernedReferenceSuitabilityError(f"{context}.provider_profiles must be a list")
        provider_profiles = tuple(
            text
            for item in provider_profiles_raw
            if (text := self._optional_text(item)) is not None
        )

        coverage_raw = value.get("coverage")
        if not isinstance(coverage_raw, dict):
            raise GovernedReferenceSuitabilityError(f"{context}.coverage must be a JSON object")
        coverage = ReferenceCoverage(
            framing_type=self._required_text(coverage_raw, "framing_type", f"{context}.coverage"),
            coverage=self._required_text(coverage_raw, "coverage", f"{context}.coverage"),
            required_features_visible=self._required_bool(
                coverage_raw,
                "required_features_visible",
                f"{context}.coverage",
            ),
            identity_visible=self._required_bool(
                coverage_raw,
                "identity_visible",
                f"{context}.coverage",
            ),
            full_required_asset_visible=self._required_bool(
                coverage_raw,
                "full_required_asset_visible",
                f"{context}.coverage",
            ),
        )

        return ShotReference(
            reference_id=reference_id,
            asset_id=asset_id,
            role=role,
            reference_class=reference_class,
            priority=priority,
            subject_type=subject_type,
            source_path=source_path,
            canonical_source_id=self._optional_text(value.get("canonical_source_id")),
            label=self._optional_text(value.get("label")) or "",
            width=width,
            height=height,
            provider_ready=provider_ready,
            provider_profiles=provider_profiles,
            coverage=coverage,
            reference_fingerprint=self._optional_text(value.get("reference_fingerprint")),
            file_checksum=declared_checksum,
            contains_subjects=self._text_tuple(value.get("contains_subjects")),
            contains_props=self._text_tuple(value.get("contains_props")),
            contains_environments=self._text_tuple(value.get("contains_environments")),
        )

    @staticmethod
    def _require_passing_plan(reference_plan: dict[str, Any], shot_id: str) -> None:
        status = str(reference_plan.get("status") or "").strip().lower()
        if not status or status == "passed":
            return
        diagnostics_raw = reference_plan.get("diagnostics", [])
        details: list[str] = []
        if isinstance(diagnostics_raw, list):
            for item in diagnostics_raw:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "").strip()
                message = str(item.get("message") or "").strip()
                detail = ": ".join(value for value in (code, message) if value)
                if detail:
                    details.append(detail)
        suffix = f" Diagnostics: {'; '.join(details)}" if details else ""
        raise GovernedReferenceSuitabilityError(
            f"Persisted governed ReferencePlan for {shot_id} has status '{status}'.{suffix}"
        )

    @staticmethod
    def _package_asset_ids(package: ProductionPackage) -> set[str]:
        values: set[str] = set()
        for asset in package.assets:
            candidates: list[object] = [asset.get("asset_id")]
            for section_name in ("production", "resolution", "binding", "governed"):
                section = asset.get(section_name)
                if isinstance(section, dict):
                    candidates.append(section.get("asset_id"))
            for candidate in candidates:
                text = str(candidate or "").strip().upper()
                if text:
                    values.add(text)
        for reference in package.references:
            text = str(reference.get("asset_id") or "").strip().upper()
            if text:
                values.add(text)
        return values

    @staticmethod
    def _required_text(value: dict[str, Any], key: str, context: str) -> str:
        text = GovernedReferenceSuitabilityService._optional_text(value.get(key))
        if text is None:
            raise GovernedReferenceSuitabilityError(f"{context}.{key} is required")
        return text

    @staticmethod
    def _optional_text(value: object) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _positive_int(value: object, field: str) -> int:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        raise GovernedReferenceSuitabilityError(f"{field} must be a positive integer")

    @staticmethod
    def _required_bool(value: dict[str, Any], key: str, context: str) -> bool:
        raw = value.get(key)
        if isinstance(raw, bool):
            return raw
        raise GovernedReferenceSuitabilityError(f"{context}.{key} must be an explicit boolean")

    @staticmethod
    def _text_tuple(value: object) -> tuple[str, ...]:
        if not isinstance(value, list | tuple):
            return ()
        return tuple(
            text
            for item in value
            if (text := GovernedReferenceSuitabilityService._optional_text(item)) is not None
        )

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
