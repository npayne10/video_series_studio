"""Q3.1.3.2 read-only provenance bridge for compiled governed ReferencePlans.

No mutation, persistence, replanning, ComfyUI submission, or production effect.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from vscs.application.acpp.reference_roles import ReferencePriority, ReferenceRole

from .h3_governed_reference_review import (
    H3GovernedReferenceReview,
    review_governed_h3_references,
)
from .h3_reference_selection_governance import (
    H3ReferenceCandidate,
    H3ReferenceGovernanceError,
)

if TYPE_CHECKING:
    from vscs.application.production_execution.package_compilation import CompiledProductionPackage
    from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection


_NON_DIRECT = frozenset(
    {
        ReferenceRole.CONTINUITY_ANCHOR,
        ReferenceRole.START_FRAME_REFERENCE,
        ReferenceRole.END_FRAME_REFERENCE,
        ReferenceRole.MOTION_REFERENCE,
        ReferenceRole.STYLE_REFERENCE,
    }
)


@dataclass(frozen=True)
class H3ReferenceProvenanceReport:
    shot_id: str
    compiled_package_fingerprint: str
    source_package_fingerprint: str
    provider_profile_fingerprint: str
    reference_plan_fingerprint: str
    reference_ids: tuple[str, ...]
    review: H3GovernedReferenceReview
    report_fingerprint: str
    advisory_only: bool = True


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    ).hexdigest()


def review_compiled_h3_reference_provenance(
    compiled: CompiledProductionPackage,
    projection: ProviderReferenceCapacityProjection,
    *,
    guide_overlap_ids: frozenset[str] = frozenset(),
) -> H3ReferenceProvenanceReport:
    """Reconcile a supplied governed projection with an immutable compiled source."""
    plan = compiled.reference_plan
    if not isinstance(plan, dict):
        raise H3ReferenceGovernanceError("Compiled package has no governed ReferencePlan")
    if plan.get("status") not in (None, "passed"):
        raise H3ReferenceGovernanceError("Compiled governed ReferencePlan did not pass")
    raw_references = plan.get("references")
    if not isinstance(raw_references, list) or not raw_references:
        raise H3ReferenceGovernanceError("Governed ReferencePlan has no reference records")
    if not all(isinstance(item, dict) for item in raw_references):
        raise H3ReferenceGovernanceError("Governed reference record is not an object")
    if not compiled.package_fingerprint or not compiled.source_package_fingerprint:
        raise H3ReferenceGovernanceError("Compiled package fingerprint is missing")
    if not projection.provider_profile_fingerprint:
        raise H3ReferenceGovernanceError("Provider profile fingerprint is missing")

    candidates: list[H3ReferenceCandidate] = []
    seen: set[str] = set()
    for reference in raw_references:
        reference_id = reference.get("reference_id")
        if not isinstance(reference_id, str) or not reference_id.strip():
            raise H3ReferenceGovernanceError("Governed reference ID missing")
        if reference_id in seen:
            raise H3ReferenceGovernanceError("Duplicate governed reference ID")
        seen.add(reference_id)
        try:
            role = ReferenceRole(reference["role"])
            priority = ReferencePriority(reference["priority"])
        except (KeyError, ValueError, TypeError) as exc:
            raise H3ReferenceGovernanceError("Invalid governed reference role or priority") from exc
        if role in _NON_DIRECT:
            continue
        kind = "other"
        role_name = role.value.lower()
        if "character" in role_name:
            kind = "character"
        elif "environment" in role_name or "location" in role_name:
            kind = "environment"
        candidates.append(
            H3ReferenceCandidate(
                reference_id=reference_id,
                kind=kind,
                required=priority is ReferencePriority.REQUIRED,
            )
        )
    # Projection in the H3 adapter is span-specific: a full-shot plan may
    # include future or indirect references. Only identical direct ID sets
    # can be reconciled without explicit span activation authority.
    direct_ids = tuple(candidate.reference_id for candidate in candidates)
    projected_ids = set(
        (*projection.selected_reference_ids, *projection.deferred_preferred_reference_ids)
    )
    if projected_ids != set(direct_ids):
        raise H3ReferenceGovernanceError(
            "Projection differs from full compiled direct references; span activation authority required"
        )
    review = review_governed_h3_references(
        projection, tuple(candidates), guide_overlap_ids=guide_overlap_ids
    )
    plan_fingerprint = _digest(plan)
    provenance: dict[str, Any] = {
        "shot_id": compiled.shot_id,
        "compiled_package_fingerprint": compiled.package_fingerprint,
        "source_package_fingerprint": compiled.source_package_fingerprint,
        "provider_profile_fingerprint": projection.provider_profile_fingerprint,
        "reference_plan_fingerprint": plan_fingerprint,
        "reference_ids": list(direct_ids),
        "review_fingerprint": review.authority_fingerprint,
    }
    return H3ReferenceProvenanceReport(
        shot_id=compiled.shot_id,
        compiled_package_fingerprint=compiled.package_fingerprint,
        source_package_fingerprint=compiled.source_package_fingerprint,
        provider_profile_fingerprint=projection.provider_profile_fingerprint,
        reference_plan_fingerprint=plan_fingerprint,
        reference_ids=direct_ids,
        review=review,
        report_fingerprint=_digest(provenance),
    )
