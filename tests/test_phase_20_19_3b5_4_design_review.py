"""Field-level decision and metadata provenance contract."""

import json

import pytest

from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
    build_reviewed_master_prompt,
)
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


def _spec():
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"layout": "Existing console"},
        master_prompt="Original prompt",
    )


def _review(spec):
    return DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        reviewer="QA operator",
        fields=(
            DesignFieldReview(
                field="layout",
                proposed_value="Existing console",
                final_value="Existing console",
                decision=DetailDecision.ACCEPT,
                origin=DetailOrigin.DESIGN_PROPOSAL,
            ),
            DesignFieldReview(
                field="scale",
                proposed_value="",
                final_value="8 m by 5 m",
                decision=DetailDecision.EDIT,
                origin=DetailOrigin.UNRESOLVED,
                rationale="Operator design choice",
            ),
            DesignFieldReview(
                field="materials",
                proposed_value="",
                final_value="",
                decision=DetailDecision.DEFER,
                origin=DetailOrigin.UNRESOLVED,
            ),
            DesignFieldReview(
                field="spatial_anchors",
                proposed_value="",
                final_value="",
                decision=DetailDecision.REJECT,
                origin=DetailOrigin.UNRESOLVED,
            ),
            DesignFieldReview(
                field="lighting",
                proposed_value="",
                final_value="",
                decision=DetailDecision.DEFER,
                origin=DetailOrigin.UNRESOLVED,
            ),
        ),
    )


def test_field_decisions_do_not_promote_deferred_details():
    spec = _spec()
    changed, audit = apply_review(spec, _review(spec))
    assert changed.canonical_attributes == {"layout": "Existing console", "scale": "8 m by 5 m"}
    payload = json.loads(audit)
    assert payload["canon_approved"] is False
    assert payload["image_authorized"] is False
    assert len(payload["fields"]) == 5
    assert payload["result_fingerprint"] == changed.fingerprint()


def test_stale_fingerprint_rejected():
    spec = _spec()
    review = _review(spec).model_copy(update={"base_fingerprint": "wrong"})
    with pytest.raises(ValueError, match="fingerprint"):
        apply_review(spec, review)


def test_prompt_only_contains_accepted_details():
    spec = _spec()
    prompt = build_reviewed_master_prompt(spec, _review(spec))
    assert "8 m by 5 m" in prompt
    assert "materials:" not in prompt
    assert "not approved" in prompt


def test_accept_requires_value_and_defer_forbids_value():
    with pytest.raises(ValueError):
        DesignFieldReview(
            field="scale", decision=DetailDecision.ACCEPT, origin=DetailOrigin.UNRESOLVED
        )
    with pytest.raises(ValueError):
        DesignFieldReview(
            field="scale",
            final_value="8 m",
            decision=DetailDecision.DEFER,
            origin=DetailOrigin.DESIGN_PROPOSAL,
        )
