"""Q3.1.3.3: read-only freshness and temporal-span provenance checks.

The caller supplies an independently refreshed compiled package. This checker
does not access a project directory, alter active slots, or approve a plan.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

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
    from vscs.application.production_execution.span_scoped_provider_inputs import (
        SpanScopedProviderInputPlan,
    )
    from vscs.application.provider_reference_capacity import ProviderReferenceCapacityProjection

    from .minimax_h3_span_adapter import MiniMaxH3SpanExecution

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
class H3SpanFreshnessReport:
    shot_id: str
    span_id: str
    package_fingerprint: str
    reference_plan_fingerprint: str
    span_input_plan_fingerprint: str
    provider_profile_fingerprint: str
    review: H3GovernedReferenceReview
    fingerprint: str
    advisory_only: bool = True


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def validate_h3_span_freshness(
    compiled: CompiledProductionPackage,
    refreshed: CompiledProductionPackage,
    span_plan: SpanScopedProviderInputPlan,
    execution: MiniMaxH3SpanExecution,
    projection: ProviderReferenceCapacityProjection,
    *,
    guide_overlap_ids: frozenset[str] = frozenset(),
) -> H3SpanFreshnessReport:
    """Fail closed if supplied current authority and span selection disagree."""
    if (
        not compiled.package_fingerprint
        or compiled.package_fingerprint != refreshed.package_fingerprint
        or compiled.source_package_fingerprint != refreshed.source_package_fingerprint
        or compiled.shot_id != refreshed.shot_id
    ):
        raise H3ReferenceGovernanceError("Compiled package source is stale")
    plan = compiled.reference_plan
    current_plan = refreshed.reference_plan
    if not isinstance(plan, dict) or not isinstance(current_plan, dict):
        raise H3ReferenceGovernanceError("Governed ReferencePlan is missing")
    if plan.get("status") not in (None, "passed") or current_plan.get("status") not in (
        None,
        "passed",
    ):
        raise H3ReferenceGovernanceError("Governed ReferencePlan is blocked")
    reference_digest = _digest(plan)
    if reference_digest != _digest(current_plan):
        raise H3ReferenceGovernanceError("Governed ReferencePlan source is stale")
    if (
        span_plan.shot_id != compiled.shot_id
        or span_plan.source_package_fingerprint != compiled.package_fingerprint
        or execution.source_span_input_plan_fingerprint != span_plan.fingerprint
    ):
        raise H3ReferenceGovernanceError("Span input plan provenance mismatch")
    matches = tuple(item for item in span_plan.spans if item.span_id == execution.span_id)
    if len(matches) != 1:
        raise H3ReferenceGovernanceError("Exact governed span is unavailable")
    span = matches[0]
    if span.sequence_number != execution.sequence_number:
        raise H3ReferenceGovernanceError("Span sequence does not match")
    active = tuple(slot.reference_id for slot in span.reference_slots)
    if active != span.active_reference_ids:
        raise H3ReferenceGovernanceError("Span active reference slots disagree")
    selected = tuple(slot.reference_id for slot in execution.reference_slots)
    if selected != projection.selected_reference_ids:
        raise H3ReferenceGovernanceError("Execution reference selection differs from projection")
    if execution.deferred_reference_ids != projection.deferred_preferred_reference_ids:
        raise H3ReferenceGovernanceError("Deferred reference IDs differ from projection")
    if len(set(active)) != len(active):
        raise H3ReferenceGovernanceError("Duplicate active reference IDs")
    if {*selected, *execution.deferred_reference_ids} != set(active):
        raise H3ReferenceGovernanceError("Future or unknown reference in provider execution")

    raw = plan.get("references")
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise H3ReferenceGovernanceError("Governed reference records invalid")
    records: dict[str, dict[str, object]] = {}
    for item in raw:
        rid = item.get("reference_id")
        if not isinstance(rid, str) or not rid.strip() or rid in records:
            raise H3ReferenceGovernanceError("Duplicate or missing governed reference ID")
        records[rid] = item
    candidates: list[H3ReferenceCandidate] = []
    for rid in active:
        record = records.get(rid)
        if record is None:
            raise H3ReferenceGovernanceError("Active reference absent from ReferencePlan")
        try:
            raw_role = record["role"]
            raw_priority = record["priority"]
            if not isinstance(raw_role, str) or not isinstance(raw_priority, str):
                raise H3ReferenceGovernanceError("Invalid governed reference role or priority")
            role = ReferenceRole(raw_role)
            priority = ReferencePriority(raw_priority)
        except (KeyError, TypeError, ValueError) as exc:
            raise H3ReferenceGovernanceError("Invalid governed reference role or priority") from exc
        if role in _NON_DIRECT or priority is ReferencePriority.OPTIONAL:
            raise H3ReferenceGovernanceError(
                "Non-direct reference cannot occupy active direct slot"
            )
        if priority is ReferencePriority.PREFERRED and record.get("provider_ready") is not True:
            raise H3ReferenceGovernanceError("Preferred direct reference is not provider ready")
        kind: Literal["character", "environment", "visual_element", "other"] = "other"
        if role in (
            ReferenceRole.PRIMARY_IDENTITY,
            ReferenceRole.SECONDARY_IDENTITY,
            ReferenceRole.GROUP_IDENTITY,
            ReferenceRole.BACKGROUND_IDENTITY,
        ):
            kind = "character"
        elif role is ReferenceRole.ENVIRONMENT_REFERENCE:
            kind = "environment"
        candidates.append(H3ReferenceCandidate(rid, kind, priority is ReferencePriority.REQUIRED))
    review = review_governed_h3_references(
        projection, tuple(candidates), guide_overlap_ids=guide_overlap_ids
    )
    evidence = {
        "shot": compiled.shot_id,
        "span": span.span_id,
        "package": compiled.package_fingerprint,
        "source": compiled.source_package_fingerprint,
        "reference_plan": reference_digest,
        "span_plan": span_plan.fingerprint,
        "profile": projection.provider_profile_fingerprint,
        "review": review.authority_fingerprint,
    }
    return H3SpanFreshnessReport(
        shot_id=compiled.shot_id,
        span_id=span.span_id,
        package_fingerprint=compiled.package_fingerprint,
        reference_plan_fingerprint=reference_digest,
        span_input_plan_fingerprint=span_plan.fingerprint,
        provider_profile_fingerprint=projection.provider_profile_fingerprint,
        review=review,
        fingerprint=_digest(evidence),
    )
