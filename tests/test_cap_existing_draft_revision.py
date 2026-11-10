"""Single-field existing Draft revision: provenance and preserved decisions."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
    build_reviewed_master_prompt,
)
from vscs.application.caps.draft_cap_revision import (
    REVISION_HISTORY_KEY,
    DraftCAPRevisionError,
    prepare_draft_cap_revision,
    save_draft_cap_field_revision,
)
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus


def _fixture():
    spec = CAPStructuredSpecification(
        asset_id="STORY-PRO-TEST",
        category=AssetCategory.PROP,
        design_intent="Diagnostic console",
        canonical_attributes={"components": "Blue display", "materials": "Graphite"},
        master_prompt="Unapproved proposal",
    )
    fields = (
        DesignFieldReview(
            field="components",
            proposed_value="Blue display",
            final_value="Blue display",
            decision=DetailDecision.ACCEPT,
            origin=DetailOrigin.DESIGN_PROPOSAL,
            evidence="Reviewed components",
        ),
        DesignFieldReview(
            field="materials",
            proposed_value="Graphite",
            final_value="Graphite",
            decision=DetailDecision.ACCEPT,
            origin=DetailOrigin.DESIGN_PROPOSAL,
            evidence="Reviewed materials",
        ),
        DesignFieldReview(
            field="geometry",
            proposed_value="Console has a blue display",
            final_value="",
            decision=DetailDecision.DEFER,
            origin=DetailOrigin.UNRESOLVED,
        ),
    )
    review = DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        reviewer="Original reviewer",
        story_fingerprint="story-current",
        context_fingerprint="context-current",
        fields=fields,
    )
    result, audit = apply_review(spec, review)
    result = result.model_copy(
        update={"master_prompt": build_reviewed_master_prompt(result, review)}
    )
    metadata = {
        SPECIFICATION_METADATA_KEY: json.dumps(result.model_dump(mode="json")),
        DESIGN_REVIEW_KEY: audit,
        "custom_property": "retain",
    }
    cap = SimpleNamespace(
        asset_id=spec.asset_id, status=CAPStatus.DRAFT, production_metadata=metadata
    )
    repo = SimpleNamespace(compare_and_swap_draft_metadata=Mock())
    caps = SimpleNamespace(
        get=Mock(return_value=cap),
        assets=SimpleNamespace(
            get=Mock(return_value=SimpleNamespace(category=AssetCategory.PROP))
        ),
        repository=repo,
    )
    batch = SimpleNamespace(
        current_story_fingerprint=Mock(return_value="story-current"),
        generator=SimpleNamespace(
            specifications=SimpleNamespace(caps=caps),
        ),
    )
    service = SimpleNamespace(
        batch=batch,
        discover=Mock(
            return_value=(
                SimpleNamespace(asset_id=spec.asset_id, has_cap=True, has_specification=True),
            )
        ),
        prepare_context=Mock(return_value=SimpleNamespace(fingerprint="context-current")),
        validate_reviewed_dependencies=Mock(),
    )
    return service, cap, repo


def test_revise_deferred_field_preserves_accepted_review_and_unrelated_metadata():
    service, cap, repo = _fixture()
    snapshot = prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)
    revised = save_draft_cap_field_revision(
        service,
        snapshot,
        field="geometry",
        reviewed_value="Operator-reviewed rectangular housing",
        rationale="Reviewed physical design for disposable reference",
        reviewer="Test operator",
    )
    assert revised.canonical_attributes["components"] == "Blue display"
    assert revised.canonical_attributes["materials"] == "Graphite"
    assert revised.canonical_attributes["geometry"] == "Operator-reviewed rectangular housing"
    kwargs = repo.compare_and_swap_draft_metadata.call_args.kwargs
    assert kwargs["expected"] == cap.production_metadata
    new_meta = kwargs["replacement"]
    assert new_meta["custom_property"] == "retain"
    audit = json.loads(new_meta[DESIGN_REVIEW_KEY])
    assert audit["canon_approved"] is False
    assert audit["image_authorized"] is False
    assert [(f["field"], f["decision"]) for f in audit["fields"]] == [
        ("components", "accept"),
        ("materials", "accept"),
        ("geometry", "edit"),
    ]
    history = json.loads(new_meta[REVISION_HISTORY_KEY])
    assert history[0]["prior_decision"] == "defer"
    assert json.loads(history[0]["prior_review_audit"])["reviewer"] == "Original reviewer"


def test_cannot_change_already_accepted_field():
    service, cap, repo = _fixture()
    snap = prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)
    with pytest.raises(DraftCAPRevisionError, match="deferred/rejected"):
        save_draft_cap_field_revision(
            service, snap, field="materials", reviewed_value="Steel",
            rationale="Would overwrite accepted value", reviewer="Operator",
        )
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_requires_nonempty_value_rationale_and_reviewer():
    service, cap, repo = _fixture()
    snap = prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)
    with pytest.raises(DraftCAPRevisionError, match="required"):
        save_draft_cap_field_revision(
            service, snap, field="geometry", reviewed_value="Rectangle",
            rationale="", reviewer="Operator",
        )
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_rejects_approved_cap_before_preparing():
    service, cap, _repo = _fixture()
    cap.status = CAPStatus.APPROVED
    with pytest.raises(DraftCAPRevisionError, match="Draft"):
        prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)


def test_rejects_stale_story_or_context_before_write():
    service, cap, repo = _fixture()
    snap = prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)
    service.batch.current_story_fingerprint.return_value = "story-changed"
    with pytest.raises(DraftCAPRevisionError, match="Story changed"):
        save_draft_cap_field_revision(
            service, snap, field="geometry", reviewed_value="Rectangle",
            rationale="Reviewed", reviewer="Operator",
        )
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_invalid_persisted_review_fails_closed():
    service, cap, _repo = _fixture()
    cap.production_metadata[DESIGN_REVIEW_KEY] = "forged"
    with pytest.raises(DraftCAPRevisionError, match="invalid"):
        prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)
