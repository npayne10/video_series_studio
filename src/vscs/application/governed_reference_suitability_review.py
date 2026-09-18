"""Approval policy for explicit governed reference-suitability reviews."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from vscs.application.acpp.reference_roles import ReferencePriority, ReferenceRole
from vscs.application.governed_reference_suitability_authoring import (
    GovernedReferenceCandidate,
    GovernedReferenceSuitabilityAuthoringError,
    GovernedReferenceSuitabilityAuthoringService,
    SuitabilityReferenceReview,
    SuitabilityReviewTarget,
)
from vscs.application.production_package import ProductionPackage


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

    def candidates_for_package(
        self,
        package: ProductionPackage,
    ) -> tuple[GovernedReferenceCandidate, ...]:
        """Return candidates with production-semantic priority suggestions."""
        return tuple(
            replace(
                candidate,
                suggested_priority=suggested_reference_priority(
                    candidate.category,
                    candidate.semantic_role,
                ),
            )
            for candidate in super().candidates_for_package(package)
        )

    def approve_and_resolve(
        self,
        package: ProductionPackage,
        *,
        target: SuitabilityReviewTarget,
        references: tuple[SuitabilityReferenceReview, ...],
    ) -> dict[str, Any]:
        self._require_complete_visual_coverage(package, references)
        self._require_character_role_alignment(package, references)
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
        characters: list[tuple[str, str]] = []
        for asset in package.assets:
            production = asset.get("production")
            view = production if isinstance(production, dict) else asset
            if str(view.get("category") or "").strip().lower() != "character":
                continue
            asset_id = cls._normalized_asset_id(view.get("asset_id"))
            if asset_id:
                characters.append((asset_id, str(view.get("role") or "").strip().lower()))
        if not characters:
            return

        primary = next(
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
        character_ids = {asset_id for asset_id, _role in characters}
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
