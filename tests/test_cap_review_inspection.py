"""Read-only integrated CAP review inspection from persisted metadata."""

import json

from PySide6.QtCore import Qt

from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
)
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.widgets.cap_review_inspection import (
    CAPReviewedSpecificationPanel,
    load_review_snapshot,
)


def _metadata():
    original = CAPStructuredSpecification(
        asset_id="STORY-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room inside unmanned vessel",
        canonical_attributes={"architecture": "Console beside workstation"},
        master_prompt="Unapproved reference prompt",
        continuity_rules=("Keep the room static.",),
    )
    review = DesignReviewPackage(
        asset_id="STORY-LOC-001",
        base_fingerprint=original.fingerprint(),
        reviewer="VSCS Acceptance Test",
        story_fingerprint="story-authority-v1",
        context_fingerprint="shot-context-v1",
        fields=(
            DesignFieldReview(
                field="architecture",
                proposed_value="Console beside workstation",
                final_value="Console beside workstation",
                decision=DetailDecision.ACCEPT,
                origin=DetailOrigin.STORY_CANDIDATE,
            ),
            DesignFieldReview(
                field="layout",
                proposed_value="Room with entry door",
                final_value="Rectangular room with one door",
                decision=DetailDecision.EDIT,
                origin=DetailOrigin.DESIGN_PROPOSAL,
            ),
            DesignFieldReview(
                field="lighting",
                proposed_value="Indicator pulses once",
                decision=DetailDecision.DEFER,
                origin=DetailOrigin.DESIGN_PROPOSAL,
                rationale="Shot event, not CAP identity",
            ),
        ),
    )
    stored = original.model_copy(
        update={
            "canonical_attributes": {
                "architecture": "Console beside workstation",
                "layout": "Rectangular room with one door",
            }
        }
    )
    audit = {
        "version": 1,
        "reviewer": review.reviewer,
        "story_fingerprint": review.story_fingerprint,
        "context_fingerprint": review.context_fingerprint,
        "base_fingerprint": review.base_fingerprint,
        "result_fingerprint": stored.fingerprint(),
        "fields": [item.model_dump(mode="json") for item in review.fields],
        "image_authorized": False,
        "canon_approved": False,
    }
    return {
        SPECIFICATION_METADATA_KEY: json.dumps(stored.model_dump(mode="json")),
        DESIGN_REVIEW_KEY: json.dumps(audit),
    }


def test_integrated_review_loads_accepted_and_deferred_decisions(qtbot):
    metadata = _metadata()
    spec, review, message = load_review_snapshot(metadata)
    assert spec is not None and review is not None
    assert "does not approve Canon" in message
    assert spec.canonical_attributes["layout"] == "Rectangular room with one door"
    assert "lighting" not in spec.canonical_attributes

    panel = CAPReviewedSpecificationPanel(metadata)
    qtbot.addWidget(panel)
    assert panel.objectName() == "capReviewedSpecificationPanel"
    assert panel.fields_table.rowCount() == 3
    assert panel.fields_table.item(1, 1).text() == "Edit"
    assert panel.fields_table.item(1, 2).text() == "Rectangular room with one door"
    assert panel.fields_table.item(2, 1).text() == "Defer"
    assert panel.fields_table.item(2, 2).text() == "—"
    assert panel.fields_table.item(2, 3).text() == "Indicator pulses once"
    assert not (panel.fields_table.item(1, 2).flags() & Qt.ItemFlag.ItemIsEditable)


def test_missing_review_never_appears_approved(qtbot):
    panel = CAPReviewedSpecificationPanel({})
    qtbot.addWidget(panel)
    assert panel.specification is None
    assert "No reviewed structured CAP" in panel.status_label.text()


def test_corrupted_audit_is_visible_without_crash(qtbot):
    metadata = _metadata()
    metadata[DESIGN_REVIEW_KEY] = "{invalid"
    panel = CAPReviewedSpecificationPanel(metadata)
    qtbot.addWidget(panel)
    assert panel.specification is None
    assert "cannot be verified" in panel.status_label.text()


def test_deferred_field_cannot_silently_become_canonical():
    metadata = _metadata()
    spec = json.loads(metadata[SPECIFICATION_METADATA_KEY])
    spec["canonical_attributes"]["lighting"] = "Approved lighting"
    metadata[SPECIFICATION_METADATA_KEY] = json.dumps(spec)
    parsed, review, message = load_review_snapshot(metadata)
    assert parsed is None and review is None
    assert "became canonical" in message


def test_missing_audit_is_reported():
    metadata = _metadata()
    metadata.pop(DESIGN_REVIEW_KEY)
    spec, review, message = load_review_snapshot(metadata)
    assert spec is None and review is None
    assert "Incomplete" in message


def test_generic_editor_preserves_governed_review_metadata():
    from vscs.presentation.widgets.cap_structured_knowledge import (
        preserve_governed_review_metadata,
    )

    original = _metadata()
    edited = {
        SPECIFICATION_METADATA_KEY: "overwritten",
        "ordinary": "updated",
    }
    preserved = preserve_governed_review_metadata(original, edited)
    assert preserved[SPECIFICATION_METADATA_KEY] == original[SPECIFICATION_METADATA_KEY]
    assert preserved[DESIGN_REVIEW_KEY] == original[DESIGN_REVIEW_KEY]
    assert preserved["ordinary"] == "updated"


def test_generic_editor_cannot_inject_review_metadata_into_new_cap():
    from vscs.presentation.widgets.cap_structured_knowledge import (
        preserve_governed_review_metadata,
    )

    result = preserve_governed_review_metadata(
        {}, {DESIGN_REVIEW_KEY: "untrusted", SPECIFICATION_METADATA_KEY: "untrusted"}
    )
    assert result == {}
