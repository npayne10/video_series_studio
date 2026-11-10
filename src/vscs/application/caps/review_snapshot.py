"""Pure persisted CAP review audit validator shared by services and UI."""

from __future__ import annotations

import json
from typing import Any

from vscs.application.caps.design_completion import DESIGN_REVIEW_KEY, DesignReviewPackage
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)


def load_review_snapshot(
    metadata: dict[str, str],
) -> tuple[CAPStructuredSpecification | None, DesignReviewPackage | None, str]:
    """Validate persisted data without changing or silently discarding invalid records."""
    spec_raw = metadata.get(SPECIFICATION_METADATA_KEY)
    review_raw = metadata.get(DESIGN_REVIEW_KEY)
    if spec_raw is None and review_raw is None:
        return None, None, "No reviewed structured CAP specification is stored."
    if spec_raw is None or review_raw is None:
        return None, None, "Incomplete stored CAP review: specification or audit is missing."
    try:
        spec = CAPStructuredSpecification.model_validate(json.loads(spec_raw))
        audit: Any = json.loads(review_raw)
        if not isinstance(audit, dict):
            raise ValueError("Review audit must be a JSON object")
        if audit.get("version") != 1:
            raise ValueError("Unsupported review audit version")
        review = DesignReviewPackage.model_validate(
            {
                "asset_id": spec.asset_id,
                "base_fingerprint": audit["base_fingerprint"],
                "fields": audit["fields"],
                "reviewer": audit["reviewer"],
                "story_fingerprint": audit.get("story_fingerprint", ""),
                "context_fingerprint": audit.get("context_fingerprint", ""),
            }
        )
        # The reviewed master prompt is rebuilt after apply_review generated
        # result_fingerprint; therefore the audit hash does not identify the
        # final serialized CAP. Validate persisted field decisions directly.
        if (
            review.asset_id != spec.asset_id
            or not audit.get("result_fingerprint")
            or audit.get("canon_approved") is not False
            or audit.get("image_authorized") is not False
        ):
            raise ValueError("Stored review identity or authority mismatch")
        for field in review.fields:
            actual = spec.canonical_attributes.get(field.field)
            if field.decision.value in {"accept", "edit"} and actual != field.final_value:
                raise ValueError(f"Reviewed field {field.field} does not match saved CAP")
            if field.decision.value in {"reject", "defer"} and actual is not None:
                raise ValueError(f"Deferred/rejected field {field.field} became canonical")
    except (ValueError, TypeError, KeyError) as exc:
        return None, None, f"Stored CAP review cannot be verified: {exc}"
    return (
        spec,
        review,
        "Persisted design review audit — this review does not approve Canon or images.",
    )
