"""Read-only Q3.1.3.1 bridge from governed capacity projection to Q3.1.3 advice.

ProviderReferenceCapacityProjection remains authoritative. This report NEVER
modifies active slots, deferred IDs, or the underlying compiled package.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection

from .h3_reference_selection_governance import (
    H3ReferenceCandidate,
    H3ReferenceGovernanceError,
    H3ReferenceProposal,
    propose_h3_reference_selection,
)


@dataclass(frozen=True)
class H3GovernedReferenceReview:
    authority_fingerprint: str
    proposal: H3ReferenceProposal
    governed_selected_ids: tuple[str, ...]
    governed_deferred_ids: tuple[str, ...]
    proposed_changes_to_governed_slots: tuple[str, ...]
    requires_operator_review: bool = True


def review_governed_h3_references(
    projection: ProviderReferenceCapacityProjection,
    candidates: tuple[H3ReferenceCandidate, ...],
    *,
    guide_overlap_ids: frozenset[str] = frozenset(),
) -> H3GovernedReferenceReview:
    """Evaluate only existing direct-slot authority, fail closed on mismatch."""
    if not projection.passed or projection.indirect_projection:
        raise H3ReferenceGovernanceError("Governed direct reference projection is not executable")
    if projection.reference_projection_mode != "direct_span_scoped_canonical_refs":
        raise H3ReferenceGovernanceError("Unsupported governed reference projection mode")
    if projection.capacity <= 0 or projection.capacity > 5:
        raise H3ReferenceGovernanceError("Unsupported H3 reference capacity")
    all_ids = tuple(candidate.reference_id for candidate in candidates)
    if len(all_ids) != len(set(all_ids)):
        raise H3ReferenceGovernanceError("Duplicate governed reference IDs")
    selected = projection.selected_reference_ids
    deferred = projection.deferred_preferred_reference_ids
    required = projection.required_reference_ids
    preferred = projection.preferred_ready_reference_ids
    if len(set(selected)) != len(selected) or len(set(deferred)) != len(deferred):
        raise H3ReferenceGovernanceError("Duplicate projection IDs")
    if len(selected) > projection.capacity or not set(required).issubset(selected):
        raise H3ReferenceGovernanceError("Required references missing or capacity exceeded")
    if set(selected) & set(deferred):
        raise H3ReferenceGovernanceError("Selected/deferred projection overlap")
    if any(item not in all_ids for item in (*selected, *deferred, *required, *preferred)):
        raise H3ReferenceGovernanceError("Projection contains unknown reference IDs")
    if any(candidate.required != (candidate.reference_id in required) for candidate in candidates):
        raise H3ReferenceGovernanceError("Candidate required flags contradict governed priorities")
    if set(guide_overlap_ids) - set(all_ids):
        raise H3ReferenceGovernanceError("Unknown guide-overlap reference")
    # The governed projector selects required IDs first, then provider-ready
    # preferred IDs in governed order. Validate provenance, never recalculate it.
    expected = (*required, *preferred[: projection.capacity - len(required)])
    expected_deferred = preferred[projection.capacity - len(required) :]
    if selected != expected or deferred != expected_deferred:
        raise H3ReferenceGovernanceError("Projection selection does not match governed precedence")
    if tuple(item for item in all_ids if item in (*selected, *deferred)) != tuple(
        item for item in all_ids if item in (*selected, *deferred)
    ):
        raise H3ReferenceGovernanceError("Reference order mismatch")
    # Advisory model may propose deferment because of guide overlap. Its result
    # cannot override the live projection even if the operator likes the advice.
    enriched = tuple(
        H3ReferenceCandidate(
            candidate.reference_id,
            candidate.kind,
            candidate.required,
            candidate.reference_id in guide_overlap_ids,
        )
        for candidate in candidates
    )
    proposal = propose_h3_reference_selection(enriched, capacity=projection.capacity)
    changes = tuple(
        item for item in selected if item in proposal.proposed_deferred_ids
    )
    authority = {
        "projection": projection.to_dict(),
        "candidate_ids": list(all_ids),
        "candidate_kinds": [item.kind for item in candidates],
        "guide_overlap_ids": sorted(guide_overlap_ids),
        "proposal_fingerprint": proposal.fingerprint,
    }
    fingerprint = hashlib.sha256(
        json.dumps(authority, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return H3GovernedReferenceReview(
        authority_fingerprint=fingerprint,
        proposal=proposal,
        governed_selected_ids=selected,
        governed_deferred_ids=deferred,
        proposed_changes_to_governed_slots=changes,
    )
