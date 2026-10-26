"""Governed Story-to-CAP specification proposals using existing CAP generation.

A provider-generated proposal is advisory, not Story Canon or CAP approval.
The operator must review suggested identity and variants before persistence.
"""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.caps.generator import CAPGeneratorService
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    CAPStructuredSpecificationService,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps.generation import GeneratedCAPDraft

_CATEGORY_KEYS: dict[AssetCategory, str] = {
    AssetCategory.CHARACTER: "anatomy",
    AssetCategory.LOCATION: "architecture",
    AssetCategory.SHIP: "silhouette",
    AssetCategory.VEHICLE: "silhouette",
    AssetCategory.PROP: "geometry",
    AssetCategory.TECHNOLOGY: "geometry",
    AssetCategory.ENVIRONMENT: "geography",
    AssetCategory.PLANET: "geography",
    AssetCategory.UNIFORM: "materials",
}


@dataclass(frozen=True)
class StoryCAPProposal:
    """Read-only specification and unverified assumptions to review."""

    specification: CAPStructuredSpecification
    suggested_attribute_key: str
    limitations: tuple[str, ...]


class StoryCAPSpecificationService:
    """Adapt existing CAP-generation providers to structured, review-first Drafts."""

    def __init__(
        self,
        generator: CAPGeneratorService,
        specifications: CAPStructuredSpecificationService,
    ) -> None:
        self.generator = generator
        self.specifications = specifications

    def propose(self, asset_id: str, approved_story_context: str) -> StoryCAPProposal:
        if not approved_story_context.strip():
            raise ValueError("Approved Story context is required")
        asset = self.generator.assets.get(asset_id)
        draft: GeneratedCAPDraft = self.generator.generate_draft(asset_id, approved_story_context)
        key = _CATEGORY_KEYS.get(asset.category, "identity")
        identity = draft.visual_identity.strip() or draft.canonical_description.strip()
        if not identity:
            raise ValueError("Provider returned no reviewable visual identity")
        description = draft.canonical_description.strip() or identity
        # The provider output is a *proposed* visual anchor; no story entailment claimed.
        prompt = (
            f"Canonical reference image of {asset.name}. {description}. "
            f"Preserve identity: {identity}. Photorealistic, physically plausible, "
            "consistent geometry and materials; clear complete subject."
        )
        proposed = CAPStructuredSpecification(
            asset_id=asset.asset_id,
            category=asset.category,
            design_intent=description,
            canonical_attributes={key: identity},
            master_prompt=prompt,
            continuity_rules=draft.continuity_rules,
            source_description="Operator-supplied approved Story context; provider draft (not verified canon)",
            origin="story_intelligence_proposal",
        )
        proposed.validate_category_contract()
        return StoryCAPProposal(
            proposed,
            key,
            (
                "Confirm that every canonical attribute is supported by the approved Story.",
                "Provider-inferred appearances and dimensions are proposals, not established canon.",
                "Review missing dependencies, variants, and prompt fidelity before saving.",
            ),
        )

    def save_reviewed(
        self, specification: CAPStructuredSpecification
    ) -> CAPStructuredSpecification:
        if specification.origin != "story_intelligence_proposal":
            raise ValueError("Only Story-to-CAP proposals are accepted by this workflow")
        if self.specifications.get(specification.asset_id) is not None:
            raise ValueError("A structured CAP already exists; revision review is required")
        return self.specifications.save_draft(specification)
