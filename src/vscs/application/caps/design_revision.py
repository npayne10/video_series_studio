"""Explicit human revisions of already-reviewed Draft CAP attributes."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    build_reviewed_master_prompt,
)
from vscs.application.caps.review_snapshot import load_review_snapshot
from vscs.application.caps.service import CAPService
from vscs.application.caps.structured_specification import SPECIFICATION_METADATA_KEY
from vscs.domain.caps import CAPStatus, CAPUpdate

REVISION_HISTORY_KEY = "vscs.cap_design_revision_history.v1"
REVISION_REFRESH_KEY = "vscs.cap_design_revision_refresh.v1"


def revise_reviewed_field(
    caps: CAPService,
    asset_id: str,
    *,
    field: str,
    final_value: str,
    reviewer: str,
    rationale: str,
    expected_fingerprint: str,
) -> None:
    """Atomically replace one reviewed field while retaining its earlier audit.

    The caller must explicitly request the operation; no visual or CAP approval
    and no derived knowledge mutation occurs here.
    """
    final_value, reviewer, rationale = (v.strip() for v in (final_value, reviewer, rationale))
    if not final_value or not reviewer or len(rationale) < 15:
        raise ValueError(
            "A nonempty revision, reviewer and rationale (15+ characters) are required"
        )
    cap = caps.get(asset_id)
    if cap.status is not CAPStatus.DRAFT:
        raise ValueError("Only Draft CAP specifications can be revised")
    spec, review, diagnostic = load_review_snapshot(cap.production_metadata)
    if spec is None or review is None:
        raise ValueError(f"Cannot revise an unverified review: {diagnostic}")
    if spec.asset_id != cap.asset_id or spec.fingerprint() != expected_fingerprint:
        raise ValueError("Reviewed specification changed; reopen the revision dialog")
    if caps.assets.get(asset_id).category != spec.category:
        raise ValueError("Asset category does not match reviewed specification")
    original = next((item for item in review.fields if item.field == field), None)
    if original is None or original.decision not in {DetailDecision.ACCEPT, DetailDecision.EDIT}:
        raise ValueError("Only previously accepted or edited fields may be revised")
    if spec.canonical_attributes[field] == final_value:
        raise ValueError("Revised value must differ from the current reviewed value")

    changed = original.model_copy(
        update={
            "final_value": final_value,
            "decision": DetailDecision.EDIT,
            "origin": DetailOrigin.OPERATOR_EDITED,
            "rationale": rationale,
            "evidence": f"Human design revision by {reviewer}; prior audit retained",
        }
    )
    fields: tuple[DesignFieldReview, ...] = tuple(
        changed if item.field == field else item for item in review.fields
    )
    revised_review = DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        fields=fields,
        reviewer=reviewer,
        story_fingerprint=review.story_fingerprint,
        context_fingerprint=review.context_fingerprint,
    )
    revised_spec = spec.model_copy(
        update={
            "canonical_attributes": {**spec.canonical_attributes, field: final_value},
        }
    )
    revised_spec = revised_spec.model_copy(
        update={
            "master_prompt": build_reviewed_master_prompt(revised_spec, revised_review),
        }
    )
    revised_spec.validate_category_contract()
    metadata = dict(cap.production_metadata)
    old_audit = json.loads(metadata[DESIGN_REVIEW_KEY])
    history = json.loads(metadata.get(REVISION_HISTORY_KEY, "[]"))
    if not isinstance(history, list):
        raise ValueError("Invalid persisted revision history")
    history.append(
        {
            "revised_at": datetime.now(UTC).isoformat(),
            "reviewer": reviewer,
            "field": field,
            "old_value": spec.canonical_attributes[field],
            "new_value": final_value,
            "rationale": rationale,
            "previous_specification": json.loads(metadata[SPECIFICATION_METADATA_KEY]),
            "previous_review_audit": old_audit,
        }
    )
    audit = {
        "version": 1,
        "reviewer": reviewer,
        "story_fingerprint": review.story_fingerprint,
        "context_fingerprint": review.context_fingerprint,
        "base_fingerprint": spec.fingerprint(),
        "result_fingerprint": revised_spec.fingerprint(),
        "fields": [item.model_dump(mode="json") for item in fields],
        "image_authorized": False,
        "canon_approved": False,
    }
    metadata[SPECIFICATION_METADATA_KEY] = revised_spec.model_dump_json(exclude_none=True)
    metadata[DESIGN_REVIEW_KEY] = json.dumps(audit, sort_keys=True)
    metadata[REVISION_HISTORY_KEY] = json.dumps(history, sort_keys=True)
    metadata[REVISION_REFRESH_KEY] = json.dumps(
        {
            "specification_fingerprint": revised_spec.fingerprint(),
            "field": field,
            "requires_guidance_refresh": True,
            "requires_knowledge_reconciliation": True,
            "requires_visual_reassessment": True,
        },
        sort_keys=True,
    )
    caps.update(asset_id, CAPUpdate(production_metadata=metadata))
