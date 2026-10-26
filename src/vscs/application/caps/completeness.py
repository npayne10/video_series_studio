"""Category-aware CAP completeness assessment; advisory Drafts cannot become masters."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory

REQUIRED_FIELDS: dict[AssetCategory, tuple[str, ...]] = {
    AssetCategory.CHARACTER: ("anatomy", "face", "proportions", "costume"),
    AssetCategory.LOCATION: ("layout", "scale", "materials", "spatial_anchors", "lighting"),
    AssetCategory.SHIP: ("dimensions", "silhouette", "hull", "markings"),
    AssetCategory.VEHICLE: ("dimensions", "silhouette", "materials", "markings"),
    AssetCategory.PROP: ("geometry", "materials", "components", "scale"),
    AssetCategory.TECHNOLOGY: ("geometry", "materials", "components", "operating_states"),
    AssetCategory.ENVIRONMENT: ("geography", "atmosphere", "illumination"),
    AssetCategory.PLANET: ("geography", "atmosphere", "illumination"),
    AssetCategory.UNIFORM: ("cut", "fabric", "colours", "insignia"),
}


@dataclass(frozen=True)
class CAPCompletenessAssessment:
    """Human-readable coverage for a category, independent of approval."""

    category: AssetCategory
    required: tuple[str, ...]
    missing: tuple[str, ...]
    unverified: tuple[str, ...]
    ready_for_image_review: bool


def assess_completeness(spec: CAPStructuredSpecification) -> CAPCompletenessAssessment:
    """Fail closed on absent fields and on unverified source authority.

    Filling a text box is not evidence that a claim belongs to Story Canon.
    """
    required = REQUIRED_FIELDS.get(spec.category, ("identity",))
    missing = tuple(key for key in required if not spec.canonical_attributes.get(key, "").strip())
    unverified = tuple(key for key in required if spec.canonical_attributes.get(key, "").strip())
    return CAPCompletenessAssessment(
        spec.category,
        required,
        missing,
        unverified,
        False,  # No claim-level source verification or approved reference authority here.
    )
