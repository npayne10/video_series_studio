"""Author explicit governed reference-suitability reviews for one Production Package."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
)
from vscs.application.governed_reference_suitability import (
    GovernedReferenceSuitabilityError,
    GovernedReferenceSuitabilityService,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.projects import ProjectNotOpenError, ProjectService


class GovernedReferenceSuitabilityAuthoringError(RuntimeError):
    """Raised when an explicit suitability review cannot be authored safely."""


@dataclass(frozen=True, slots=True)
class GovernedReferenceCandidate:
    """One governed canonical reference offered for explicit human review."""

    asset_id: str
    semantic_role: str
    category: str
    source_path: str
    canonical_source_id: str
    label: str
    suggested_role: ReferenceRole
    suggested_reference_class: ReferenceClass
    suggested_subject_type: ReferenceSubjectType
    suggested_priority: ReferencePriority
    file_checksum: str | None


@dataclass(frozen=True, slots=True)
class SuitabilityReviewTarget:
    width: int = 1280
    height: int = 720
    profile_id: str = "production-video-16x9"
    provider_id: str | None = "ltx23-local"
    aspect_tolerance: float = 0.03


@dataclass(frozen=True, slots=True)
class SuitabilityReferenceReview:
    reference_id: str
    asset_id: str | None
    role: ReferenceRole
    reference_class: ReferenceClass
    subject_type: ReferenceSubjectType
    priority: ReferencePriority
    source_path: str
    canonical_source_id: str | None
    label: str
    width: int
    height: int
    provider_ready: bool
    provider_profiles: tuple[str, ...]
    framing_type: str
    coverage: str
    required_features_visible: bool
    identity_visible: bool
    full_required_asset_visible: bool
    contains_subjects: tuple[str, ...] = ()
    contains_props: tuple[str, ...] = ()
    contains_environments: tuple[str, ...] = ()
    review_note: str = ""


class GovernedReferenceSuitabilityAuthoringService:
    """Build and persist explicit reviews without inventing provider-readiness facts."""

    def __init__(
        self,
        projects: ProjectService,
        suitability: GovernedReferenceSuitabilityService | None = None,
    ) -> None:
        self.projects = projects
        self.suitability = suitability or GovernedReferenceSuitabilityService(projects)

    @property
    def project_directory(self) -> Path:
        if self.projects.project_directory is None:
            raise ProjectNotOpenError("No VSCS project is currently open")
        return self.projects.project_directory

    def review_file(self, shot_id: str) -> Path:
        return self.suitability.suitability_file(shot_id)

    def candidates_for_package(
        self,
        package: ProductionPackage,
    ) -> tuple[GovernedReferenceCandidate, ...]:
        """Return governed canonical candidates; none are automatically provider-ready."""
        asset_views = self._asset_views(package)
        candidates: list[GovernedReferenceCandidate] = []
        seen: set[tuple[str, str]] = set()

        for asset_id, view in asset_views.items():
            semantic_role = str(view.get("role") or "").strip()
            category = str(
                view.get("category")
                or view.get("expected_category")
                or view.get("asset_category")
                or "other"
            ).strip()
            canonical_values = self._canonical_paths(view)
            if not canonical_values:
                canonical_values = self._reference_paths_for_asset(package, asset_id)
            for raw_path in canonical_values:
                source = self._resolve_path(raw_path)
                key = (asset_id, os.path.normcase(str(source)))
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    GovernedReferenceCandidate(
                        asset_id=asset_id,
                        semantic_role=semantic_role,
                        category=category,
                        source_path=str(source),
                        canonical_source_id=asset_id,
                        label=self._candidate_label(asset_id, semantic_role),
                        suggested_role=self._suggested_role(category, semantic_role),
                        suggested_reference_class=ReferenceClass.CANONICAL_MASTER,
                        suggested_subject_type=self._subject_type(category),
                        suggested_priority=ReferencePriority.REQUIRED,
                        file_checksum=self._sha256_file(source) if source.is_file() else None,
                    )
                )

        # Some legacy packages expose canonical references only in package.references.
        for reference in package.references:
            asset_id = self._normalized_asset_id(reference.get("asset_id"))
            raw_path = str(reference.get("canonical_reference") or "").strip()
            if not asset_id or not raw_path:
                continue
            source = self._resolve_path(raw_path)
            key = (asset_id, os.path.normcase(str(source)))
            if key in seen:
                continue
            seen.add(key)
            view = asset_views.get(asset_id, {})
            semantic_role = str(view.get("role") or "").strip()
            category = str(view.get("category") or view.get("expected_category") or "other").strip()
            candidates.append(
                GovernedReferenceCandidate(
                    asset_id=asset_id,
                    semantic_role=semantic_role,
                    category=category,
                    source_path=str(source),
                    canonical_source_id=asset_id,
                    label=self._candidate_label(asset_id, semantic_role),
                    suggested_role=self._suggested_role(category, semantic_role),
                    suggested_reference_class=ReferenceClass.CANONICAL_MASTER,
                    suggested_subject_type=self._subject_type(category),
                    suggested_priority=ReferencePriority.REQUIRED,
                    file_checksum=self._sha256_file(source) if source.is_file() else None,
                )
            )

        return tuple(candidates)

    def load_review(self, shot_id: str) -> dict[str, Any] | None:
        path = self.review_file(shot_id)
        if not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GovernedReferenceSuitabilityAuthoringError(
                f"Unable to read governed reference suitability review {path.name}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise GovernedReferenceSuitabilityAuthoringError(
                f"Governed reference suitability review {path.name} must contain a JSON object"
            )
        return value

    def save_review(
        self,
        package: ProductionPackage,
        *,
        target: SuitabilityReviewTarget,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> Path:
        """Persist the explicit review artifact atomically; do not resolve the final plan."""
        if target.width <= 0 or target.height <= 0:
            raise GovernedReferenceSuitabilityAuthoringError(
                "Reference suitability target dimensions must be positive"
            )
        if not target.profile_id.strip():
            raise GovernedReferenceSuitabilityAuthoringError(
                "Reference suitability target profile is required"
            )
        if target.aspect_tolerance <= 0:
            raise GovernedReferenceSuitabilityAuthoringError(
                "Reference suitability aspect tolerance must be positive"
            )
        if not references:
            raise GovernedReferenceSuitabilityAuthoringError(
                "Select at least one reviewed reference before saving suitability authority"
            )

        governed_asset_ids = self._package_asset_ids(package)
        reference_ids: set[str] = set()
        payload_references: list[dict[str, Any]] = []
        for review in references:
            reference_id = review.reference_id.strip()
            if not reference_id:
                raise GovernedReferenceSuitabilityAuthoringError(
                    "Every reviewed reference requires a reference ID"
                )
            if reference_id in reference_ids:
                raise GovernedReferenceSuitabilityAuthoringError(
                    f"Duplicate reviewed reference ID: {reference_id}"
                )
            reference_ids.add(reference_id)

            asset_id = self._normalized_asset_id(review.asset_id)
            if asset_id and asset_id not in governed_asset_ids:
                raise GovernedReferenceSuitabilityAuthoringError(
                    f"Reference '{reference_id}' uses asset '{asset_id}' which is not governed "
                    "by the current Production Package"
                )
            self._require_governed_coverage_ids(
                reference_id,
                governed_asset_ids,
                (*review.contains_subjects, *review.contains_props, *review.contains_environments),
            )

            source = self._resolve_path(review.source_path)
            if not source.is_file():
                raise GovernedReferenceSuitabilityAuthoringError(
                    f"Reference '{reference_id}' source file does not exist: {source}"
                )
            if review.width <= 0 or review.height <= 0:
                raise GovernedReferenceSuitabilityAuthoringError(
                    f"Reference '{reference_id}' requires positive reviewed dimensions"
                )
            provider_profiles = tuple(
                value.strip() for value in review.provider_profiles if value.strip()
            )
            payload_references.append(
                {
                    "reference_id": reference_id,
                    "asset_id": asset_id or None,
                    "role": review.role.value,
                    "reference_class": review.reference_class.value,
                    "subject_type": review.subject_type.value,
                    "priority": review.priority.value,
                    "source_path": str(source),
                    "canonical_source_id": (review.canonical_source_id or "").strip() or None,
                    "label": review.label.strip(),
                    "width": review.width,
                    "height": review.height,
                    "file_checksum": self._sha256_file(source),
                    "provider_ready": review.provider_ready,
                    "provider_profiles": list(provider_profiles),
                    "coverage": {
                        "framing_type": review.framing_type.strip() or "unknown",
                        "coverage": review.coverage.strip() or "unknown",
                        "required_features_visible": review.required_features_visible,
                        "identity_visible": review.identity_visible,
                        "full_required_asset_visible": review.full_required_asset_visible,
                    },
                    "contains_subjects": list(review.contains_subjects),
                    "contains_props": list(review.contains_props),
                    "contains_environments": list(review.contains_environments),
                    "review_note": review.review_note.strip(),
                }
            )

        payload = {
            "schema_version": GovernedReferenceSuitabilityService.SCHEMA_VERSION,
            "shot_id": package.shot_id.strip().upper(),
            "target": {
                "width": target.width,
                "height": target.height,
                "profile_id": target.profile_id.strip(),
                "provider_id": (target.provider_id or "").strip() or None,
                "aspect_tolerance": target.aspect_tolerance,
            },
            "references": payload_references,
        }
        path = self.review_file(package.shot_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def approve_and_resolve(
        self,
        package: ProductionPackage,
        *,
        target: SuitabilityReviewTarget,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> dict[str, Any]:
        """Save the explicit review, then resolve/persist through the governed service."""
        self.save_review(package, target=target, references=references)
        try:
            plan = self.suitability.ensure_for_package(package)
        except GovernedReferenceSuitabilityError:
            raise
        if plan is None:
            raise GovernedReferenceSuitabilityAuthoringError(
                f"Governed ReferencePlan for {package.shot_id} was not produced"
            )
        return plan

    def make_reference_id(
        self,
        *,
        asset_id: str | None,
        source_path: str,
        role: ReferenceRole,
    ) -> str:
        asset = self._normalized_asset_id(asset_id)
        if asset:
            return f"LIVE-{role.value.upper()}-{asset}"
        digest = hashlib.sha256(str(self._resolve_path(source_path)).encode("utf-8")).hexdigest()[
            :12
        ]
        return f"LIVE-{role.value.upper()}-{digest.upper()}"

    def _asset_views(self, package: ProductionPackage) -> dict[str, dict[str, Any]]:
        values: dict[str, dict[str, Any]] = {}
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            asset_id = self._normalized_asset_id(view.get("asset_id"))
            if asset_id:
                values[asset_id] = view
        return values

    @staticmethod
    def _canonical_paths(view: dict[str, Any]) -> tuple[str, ...]:
        paths: list[str] = []
        direct = str(view.get("canonical_reference") or "").strip()
        if direct:
            paths.append(direct)
        many = view.get("canonical_references")
        if isinstance(many, list | tuple):
            for item in many:
                if isinstance(item, dict):
                    value = str(
                        item.get("path")
                        or item.get("canonical_reference")
                        or item.get("source_path")
                        or ""
                    ).strip()
                else:
                    value = str(item or "").strip()
                if value:
                    paths.append(value)
        return tuple(dict.fromkeys(paths))

    @staticmethod
    def _reference_paths_for_asset(
        package: ProductionPackage,
        asset_id: str,
    ) -> tuple[str, ...]:
        values = [
            str(reference.get("canonical_reference") or "").strip()
            for reference in package.references
            if str(reference.get("asset_id") or "").strip().upper() == asset_id
        ]
        return tuple(dict.fromkeys(value for value in values if value))

    def _resolve_path(self, value: str | Path) -> Path:
        raw = str(value).strip()
        path = Path(raw.replace("\\", "/")).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        return path.resolve(strict=False)

    @classmethod
    def _package_asset_ids(cls, package: ProductionPackage) -> set[str]:
        values = set(cls._asset_views_static(package))
        values.update(
            asset_id
            for reference in package.references
            if (asset_id := cls._normalized_asset_id(reference.get("asset_id")))
        )
        return values

    @classmethod
    def _asset_views_static(cls, package: ProductionPackage) -> dict[str, dict[str, Any]]:
        values: dict[str, dict[str, Any]] = {}
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            asset_id = cls._normalized_asset_id(view.get("asset_id"))
            if asset_id:
                values[asset_id] = view
        return values

    @staticmethod
    def _require_governed_coverage_ids(
        reference_id: str,
        governed_asset_ids: set[str],
        values: tuple[str, ...],
    ) -> None:
        invalid = sorted(
            {
                normalized
                for value in values
                if (
                    normalized := GovernedReferenceSuitabilityAuthoringService._normalized_asset_id(
                        value
                    )
                )
                and normalized not in governed_asset_ids
            }
        )
        if invalid:
            raise GovernedReferenceSuitabilityAuthoringError(
                f"Reference '{reference_id}' declares coverage for assets not governed by the "
                f"current Production Package: {', '.join(invalid)}"
            )

    @staticmethod
    def _candidate_label(asset_id: str, semantic_role: str) -> str:
        return f"{asset_id} — {semantic_role}" if semantic_role else asset_id

    @staticmethod
    def _suggested_role(category: str, semantic_role: str) -> ReferenceRole:
        normalized_category = category.strip().lower()
        normalized_role = semantic_role.strip().lower()
        if normalized_category == "character":
            if any(
                marker in normalized_role
                for marker in ("dialogue speaker", "primary", "lead", "principal")
            ):
                return ReferenceRole.PRIMARY_IDENTITY
            return ReferenceRole.SECONDARY_IDENTITY
        if normalized_category in {"environment", "location", "planet", "set"}:
            return ReferenceRole.ENVIRONMENT_REFERENCE
        if normalized_category == "prop":
            return ReferenceRole.PROP_REFERENCE
        if normalized_category == "furniture":
            return ReferenceRole.FURNITURE_REFERENCE
        if normalized_category in {"ship", "vehicle"}:
            return ReferenceRole.BACKGROUND_IDENTITY
        return ReferenceRole.BACKGROUND_IDENTITY

    @staticmethod
    def _subject_type(category: str) -> ReferenceSubjectType:
        normalized = category.strip().lower()
        aliases = {
            "character": ReferenceSubjectType.CHARACTER,
            "environment": ReferenceSubjectType.ENVIRONMENT,
            "location": ReferenceSubjectType.ENVIRONMENT,
            "planet": ReferenceSubjectType.ENVIRONMENT,
            "set": ReferenceSubjectType.ENVIRONMENT,
            "prop": ReferenceSubjectType.PROP,
            "furniture": ReferenceSubjectType.FURNITURE,
            "vehicle": ReferenceSubjectType.VEHICLE,
            "ship": ReferenceSubjectType.SHIP,
            "effect": ReferenceSubjectType.EFFECT,
        }
        return aliases.get(normalized, ReferenceSubjectType.OTHER)

    @staticmethod
    def _normalized_asset_id(value: object) -> str:
        return str(value or "").strip().upper()

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
