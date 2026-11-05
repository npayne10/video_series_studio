"""B.5.26: offline, read-only candidate MASTER preparation from reviewed CAPs.

This is a preparation/quality boundary, not an image generator or approval path.
The existing canonical reference library owns candidate, approval and lock actions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from vscs.application.caps.design_completion import DESIGN_REVIEW_KEY
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CanonicalAssetProfile, CAPStatus, CanonicalReferenceView

_REQUIRED_VISUAL_FIELDS: dict[AssetCategory, tuple[str, ...]] = {
    AssetCategory.SHIP: ("silhouette",),
    AssetCategory.VEHICLE: ("silhouette",),
    AssetCategory.LOCATION: ("layout", "architecture"),
    AssetCategory.PROP: ("geometry", "components", "display"),
    AssetCategory.TECHNOLOGY: ("geometry", "components", "display"),
}
_UNRESOLVED = ("unresolved", "unknown", "unspecified", "not established", "not defined")


@dataclass(frozen=True, slots=True)
class VisualIdentityPreparation:
    asset_id: str
    title: str
    category: AssetCategory
    specification_fingerprint: str
    review_fingerprint: str
    accepted_fields: tuple[tuple[str, str], ...]
    deferred_fields: tuple[str, ...]
    continuity_context: tuple[str, ...]
    dependency_asset_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    master_candidate_prompt: str
    negative_prompt: str
    required_reference_views: tuple[CanonicalReferenceView, ...]
    missing_reference_views: tuple[CanonicalReferenceView, ...]
    generation_mode: str = "local_preferred"

    @property
    def ready_for_master_candidate(self) -> bool:
        return not self.blockers

    @property
    def provider_calls(self) -> int:
        return 0


def prepare_visual_identity(
    cap: CanonicalAssetProfile,
    required_views: tuple[CanonicalReferenceView, ...],
    present_views: tuple[CanonicalReferenceView, ...] = (),
) -> VisualIdentityPreparation:
    """Use persisted reviewed fields only. No writes, AI calls or assumed approvals."""
    blockers: list[str] = []
    metadata = cap.production_metadata
    spec: CAPStructuredSpecification | None = None
    audit: dict[str, object] | None = None
    try:
        spec_text = metadata.get(SPECIFICATION_METADATA_KEY)
        audit_text = metadata.get(DESIGN_REVIEW_KEY)
        if not spec_text or not audit_text:
            raise ValueError("Governed reviewed CAP specification or decision audit is missing")
        spec = CAPStructuredSpecification.model_validate(json.loads(spec_text))
        raw_audit = json.loads(audit_text)
        if not isinstance(raw_audit, dict):
            raise ValueError("Decision audit is not an object")
        audit = raw_audit
        if spec.asset_id != cap.asset_id:
            raise ValueError("CAP specification asset identity differs from profile")
        if audit.get("version") != 1 or not audit.get("result_fingerprint"):
            raise ValueError("Design review audit is invalid or incomplete")
        if audit.get("image_authorized") is not False:
            raise ValueError("Design review unexpectedly contains image authority")
        decisions = audit.get("fields")
        if not isinstance(decisions, list):
            raise ValueError("Design decision records are missing")
        accepted_keys: set[str] = set()
        deferred_keys: set[str] = set()
        for decision in decisions:
            if not isinstance(decision, dict):
                raise ValueError("Malformed CAP field decision")
            field = decision.get("field")
            kind = decision.get("decision")
            if not isinstance(field, str) or not field:
                raise ValueError("Invalid field name in review")
            if kind in ("accept", "edit"):
                if decision.get("final_value") != spec.canonical_attributes.get(field):
                    raise ValueError("Persisted accepted design differs from review decision")
                accepted_keys.add(field)
            elif kind in ("reject", "defer"):
                if field in spec.canonical_attributes:
                    raise ValueError("Rejected/deferred design unexpectedly persisted")
                deferred_keys.add(field)
            else:
                raise ValueError("Unknown design decision")
        if set(spec.canonical_attributes) != accepted_keys:
            raise ValueError("CAP includes fields without accepted review decisions")
        if spec.category.value != cap.production_metadata.get("vscs.category", spec.category.value):
            raise ValueError("CAP category evidence mismatch")
        accepted = tuple(sorted(spec.canonical_attributes.items()))
        deferred = tuple(sorted(deferred_keys))
    except (TypeError, ValueError, KeyError) as exc:
        blockers.append(f"Reviewed specification is not verifiable: {exc}")
        accepted = ()
        deferred = ()
    if cap.status is not CAPStatus.DRAFT:
        blockers.append("B.5.26 preparation is limited to reviewed Draft CAPs")

    category = spec.category if spec is not None else AssetCategory.OTHER
    required = _REQUIRED_VISUAL_FIELDS.get(category, ())
    if required and not any(
        key in dict(accepted) and not any(term in dict(accepted)[key].lower() for term in _UNRESOLVED)
        for key in required
    ):
        blockers.append(
            f"{category.value.title()} visual identity is unresolved. Review a distinctive "
            f"physical design before generating a MASTER candidate."
        )
    if spec is not None and category is AssetCategory.SHIP and "silhouette" in deferred:
        if not any("visual identity is unresolved" in item for item in blockers):
            blockers.append("Ship silhouette is deferred; establish and review exterior identity first")

    source_hash = spec.fingerprint() if spec is not None else ""
    review_hash = (
        hashlib.sha256(metadata[DESIGN_REVIEW_KEY].encode("utf-8")).hexdigest()
        if DESIGN_REVIEW_KEY in metadata
        else ""
    )
    details = "; ".join(f"{key}: {value}" for key, value in accepted)
    if not details:
        details = "(No approved-for-Draft physical design decisions)"
    prompt = (
        f"PROPOSED MASTER REFERENCE CANDIDATE — NOT APPROVED. "
        f"Single {category.value} asset: {cap.title}. "
        f"Use only these human-reviewed Draft design decisions: {details}. "
        "Preserve asset category identity, physical geometry, materials and stable appearance. "
        "Do not add unreviewed features, internal assets as exterior silhouette, "
        "temporary Shot actions, characters, extra signage, or unsupported equipment. "
        "Related assets retain separate canonical identities; do not invent their "
        "physical appearance from containment or adjacency alone. "
        "Unresolved/deferred features are NOT authoritative; do not guess them. "
        "Neutral studio reference, complete subject visible, reproducible framing."
    )
    negative = (
        "identity substitution, extra assets, invented silhouette, unreviewed markings, "
        "changed dimensions, temporary blinking or pulse, cinematic scene, "
        "text overlays, unverified attachments, inconsistent geometry"
    )
    missing = tuple(view for view in required_views if view not in present_views)
    return VisualIdentityPreparation(
        asset_id=cap.asset_id,
        title=cap.title,
        category=category,
        specification_fingerprint=source_hash,
        review_fingerprint=review_hash,
        accepted_fields=accepted,
        deferred_fields=deferred,
        continuity_context=spec.continuity_rules if spec is not None else (),
        dependency_asset_ids=spec.dependency_asset_ids if spec is not None else (),
        blockers=tuple(blockers),
        master_candidate_prompt=prompt,
        negative_prompt=negative,
        required_reference_views=required_views,
        missing_reference_views=missing,
    )
