"""Approval policy for explicit governed reference-suitability reviews."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from vscs.application.acpp.reference_roles import ReferencePriority, ReferenceRole
from vscs.application.governed_reference_suitability import GovernedReferenceSuitabilityService
from vscs.application.governed_reference_suitability_authoring import (
    GovernedReferenceCandidate,
    GovernedReferenceSuitabilityAuthoringError,
    GovernedReferenceSuitabilityAuthoringService,
    SuitabilityReferenceReview,
    SuitabilityReviewTarget,
)
from vscs.application.production_execution.provider_policy_profiles import (
    ProviderPolicyProfileRegistry,
)
from vscs.application.production_package import ProductionPackage
from vscs.application.projects import ProjectService
from vscs.application.provider_reference_capacity import (
    ProviderReferenceCapacityProjection,
    project_provider_reference_capacity,
)


def suggested_reference_priority(
    category: str,
    semantic_role: str,
) -> ReferencePriority:
    """Suggest execution priority from governed Shot semantics.

    Identity-bearing characters and the primary location/set remain required.
    Contextual environment/planet/vehicle/ship references are preferred unless
    their governed semantic role explicitly marks them as visible or shot-critical.

    This is a suggestion only. Existing explicit review authority is never
    rewritten silently; the operator must apply and approve any change.
    """
    normalized_category = category.strip().lower()
    normalized_role = semantic_role.strip().lower()

    if normalized_category in {"character", "location", "set"}:
        return ReferencePriority.REQUIRED

    if any(
        marker in normalized_role
        for marker in (
            "required",
            "critical",
            "hero",
            "foreground",
            "visible",
            "interaction",
            "interacting",
            "held",
            "used",
        )
    ):
        return ReferencePriority.REQUIRED

    return ReferencePriority.PREFERRED


class GovernedReferenceSuitabilityReviewService(GovernedReferenceSuitabilityAuthoringService):
    """Require complete governed visual coverage before approving a ReferencePlan."""

    def __init__(
        self,
        projects: ProjectService,
        suitability: GovernedReferenceSuitabilityService | None = None,
        *,
        provider_policies: ProviderPolicyProfileRegistry | None = None,
    ) -> None:
        super().__init__(projects, suitability)
        self.provider_policies = provider_policies

    def candidates_for_package(
        self,
        package: ProductionPackage,
    ) -> tuple[GovernedReferenceCandidate, ...]:
        """Return candidates with aligned identity-role and priority suggestions."""
        primary_character = self._primary_character_asset_id(package)
        values: list[GovernedReferenceCandidate] = []
        for candidate in super().candidates_for_package(package):
            role = candidate.suggested_role
            if candidate.category.strip().lower() == "character":
                role = (
                    ReferenceRole.PRIMARY_IDENTITY
                    if candidate.asset_id == primary_character
                    else ReferenceRole.SECONDARY_IDENTITY
                )
            values.append(
                replace(
                    candidate,
                    suggested_role=role,
                    suggested_priority=suggested_reference_priority(
                        candidate.category,
                        candidate.semantic_role,
                    ),
                )
            )
        return tuple(values)

    def capacity_projection(
        self,
        target: SuitabilityReviewTarget,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> ProviderReferenceCapacityProjection | None:
        """Return installed-provider capacity projection for the explicit review."""
        if self.provider_policies is None:
            return None
        provider_id = (target.provider_id or "").strip()
        if not provider_id:
            raise GovernedReferenceSuitabilityAuthoringError(
                "Reference suitability requires an installed provider selection"
            )
        profiles = self.provider_policies.for_provider(provider_id)
        if len(profiles) != 1:
            if not profiles:
                raise GovernedReferenceSuitabilityAuthoringError(
                    f"Reference suitability provider is not installed: {provider_id}"
                )
            raise GovernedReferenceSuitabilityAuthoringError(
                f"Reference suitability provider is ambiguous: {provider_id}"
            )
        return project_provider_reference_capacity(profiles[0], references)

    def save_review(
        self,
        package: ProductionPackage,
        *,
        target: SuitabilityReviewTarget,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> Path:
        """Persist explicit review plus deterministic provider-capacity projection."""
        path = super().save_review(package, target=target, references=references)
        projection = self.capacity_projection(target, references)
        if projection is None:
            return path

        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["provider_capacity_projection"] = projection.to_dict()
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
        self._require_complete_visual_coverage(package, references)
        self._require_character_role_alignment(package, references)
        projection = self.capacity_projection(target, references)
        if projection is not None and not projection.passed:
            raise GovernedReferenceSuitabilityAuthoringError(
                "Provider direct-reference capacity blocks approval: "
                f"{projection.blocked_reason}"
            )
        return super().approve_and_resolve(package, target=target, references=references)

    @classmethod
    def _require_complete_visual_coverage(
        cls,
        package: ProductionPackage,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> None:
        required = cls._required_visual_asset_ids(package)
        if not required:
            return
        covered: set[str] = set()
        for review in references:
            direct = cls._normalized_asset_id(review.asset_id)
            if direct:
                covered.add(direct)
            covered.update(
                normalized
                for value in (
                    *review.contains_subjects,
                    *review.contains_props,
                    *review.contains_environments,
                )
                if (normalized := cls._normalized_asset_id(value))
            )
        missing = sorted(required - covered)
        if missing:
            raise GovernedReferenceSuitabilityAuthoringError(
                f"Explicit suitability review for {package.shot_id} does not cover governed "
                "visual assets: "
                + ", ".join(missing)
                + ". Include reviewed references or a composition/group reference whose "
                "contains_* coverage names those asset IDs."
            )

    @classmethod
    def _require_character_role_alignment(
        cls,
        package: ProductionPackage,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> None:
        character_ids = {
            asset_id for asset_id, _semantic_role in cls._character_records(package)
        }
        if not character_ids:
            return
        primary = cls._primary_character_asset_id(package)

        for review in references:
            asset_id = cls._normalized_asset_id(review.asset_id)
            if asset_id not in character_ids or review.role is ReferenceRole.GROUP_IDENTITY:
                continue
            expected = (
                ReferenceRole.PRIMARY_IDENTITY
                if asset_id == primary
                else ReferenceRole.SECONDARY_IDENTITY
            )
            if review.role is not expected:
                raise GovernedReferenceSuitabilityAuthoringError(
                    f"Explicit suitability reference for governed character {asset_id} uses role "
                    f"'{review.role.value}', but current Shot semantics require "
                    f"'{expected.value}'."
                )

    @classmethod
    def _primary_character_asset_id(cls, package: ProductionPackage) -> str | None:
        characters = cls._character_records(package)
        if not characters:
            return None
        return next(
            (
                asset_id
                for asset_id, semantic_role in characters
                if any(
                    marker in semantic_role
                    for marker in ("dialogue speaker", "primary", "lead", "principal")
                )
            ),
            characters[0][0],
        )

    @classmethod
    def _character_records(
        cls,
        package: ProductionPackage,
    ) -> tuple[tuple[str, str], ...]:
        values: list[tuple[str, str]] = []
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            if str(view.get("category") or "").strip().lower() != "character":
                continue
            asset_id = cls._normalized_asset_id(view.get("asset_id"))
            if asset_id:
                values.append((asset_id, str(view.get("role") or "").strip().lower()))
        return tuple(values)

    @classmethod
    def _required_visual_asset_ids(cls, package: ProductionPackage) -> set[str]:
        required = {
            normalized
            for reference in package.references
            if (normalized := cls._normalized_asset_id(reference.get("asset_id")))
        }
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            asset_id = cls._normalized_asset_id(view.get("asset_id"))
            if not asset_id:
                continue
            canonical = str(view.get("canonical_reference") or "").strip()
            canonical_many = view.get("canonical_references")
            if canonical or (isinstance(canonical_many, list | tuple) and canonical_many):
                required.add(asset_id)
        return required
