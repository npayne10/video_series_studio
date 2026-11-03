"""B.5.21C reviewed Draft preflight, provenance, and rollback acceptance."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
)
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.story_batch import StoryBatchError
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus
from vscs.presentation.dialogs.cap_detail_review_dialog import CAPDetailReviewDialog


def _spec():
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Quiet engineering room",
        canonical_attributes={
            "architecture": "A vessel interior",
            "materials": "Unknown surface",
        },
        master_prompt="Draft only",
        origin="story_intelligence_proposal",
    )


def _review(spec, *, context="context-v1", story="story-v1", include_architecture=True):
    fields = [
        DesignFieldReview(
            field=field,
            proposed_value=value,
            final_value=value,
            decision=DetailDecision.EDIT,
            origin=DetailOrigin.DESIGN_PROPOSAL,
        )
        for field, value in spec.canonical_attributes.items()
        if include_architecture or field != "architecture"
    ]
    fields.extend(
        DesignFieldReview(
            field=field,
            decision=DetailDecision.DEFER,
            origin=DetailOrigin.UNRESOLVED,
        )
        for field in ("layout", "scale", "spatial_anchors", "lighting")
    )
    return DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        fields=tuple(fields),
        reviewer="Operator",
        story_fingerprint=story,
        context_fingerprint=context,
    )


def _service():
    caps = Mock()
    caps.get.side_effect = CAPNotFoundError("Missing CAP")
    caps.assets.get.return_value = SimpleNamespace(
        asset_id="CAP-LOC-001",
        name="Engineering control room",
        category=AssetCategory.LOCATION,
    )
    specifications = Mock()
    specifications.get.return_value = None
    specifications.caps = caps
    batch = Mock()
    batch.current_story_fingerprint.return_value = "story-v1"
    batch.generator.specifications = specifications
    service = StoryCAPBatchReviewService(batch)
    service.prepare_context = Mock(return_value=SimpleNamespace(fingerprint="context-v1"))
    service.validate_reviewed_dependencies = Mock(return_value=())
    return service, caps, specifications


def test_reviewed_all_populated_details_required():
    spec = _spec()
    with pytest.raises(ValueError, match="Every populated CAP attribute"):
        apply_review(spec, _review(spec, include_architecture=False))


def test_review_audit_keeps_context_and_unapproved_authority():
    spec = _spec()
    reviewed, audit_text = apply_review(spec, _review(spec))
    audit = json.loads(audit_text)
    assert reviewed.category is AssetCategory.LOCATION
    assert audit["context_fingerprint"] == "context-v1"
    assert audit["story_fingerprint"] == "story-v1"
    assert not audit["canon_approved"]
    assert not audit["image_authorized"]


@pytest.mark.parametrize(
    ("context", "actual", "story"),
    [
        ("", "context-v1", "story-v1"),
        ("old-context", "context-v1", "story-v1"),
        ("context-v1", "changed-context", "story-v1"),
        ("context-v1", "context-v1", "old-story"),
    ],
)
def test_stale_review_rejected_before_any_cap_write(context, actual, story):
    service, caps, _specifications = _service()
    service.prepare_context.return_value.fingerprint = actual
    spec = _spec()
    with pytest.raises(StoryBatchError, match="fingerprint|context changed"):
        service.save_reviewed(
            "STORY-001",
            spec,
            "story-v1",
            _review(spec, context=context, story=story),
            expected_context_fingerprint="context-v1",
        )
    caps.create.assert_not_called()
    caps.update.assert_not_called()
    caps.delete.assert_not_called()


def test_current_review_commits_only_draft_with_context_gate():
    service, caps, _specifications = _service()
    spec = _spec()
    with patch("vscs.application.caps.story_batch_review.DesignReviewPersistence") as persist:
        service.save_reviewed(
            "STORY-001",
            spec,
            "story-v1",
            _review(spec),
            expected_context_fingerprint="context-v1",
        )
    caps.create.assert_called_once()
    assert caps.create.call_args.args[0].status is CAPStatus.DRAFT
    persist.return_value.save.assert_called_once()
    service.prepare_context.assert_called_once_with("STORY-001", spec.asset_id)
    caps.delete.assert_not_called()


def test_persistence_failure_rolls_back_newly_created_empty_draft():
    service, caps, _specifications = _service()
    spec = _spec()
    with patch("vscs.application.caps.story_batch_review.DesignReviewPersistence") as persist:
        persist.return_value.save.side_effect = RuntimeError("Storage failed")
        with pytest.raises(RuntimeError, match="Storage failed"):
            service.save_reviewed(
                "STORY-001",
                spec,
                "story-v1",
                _review(spec),
                expected_context_fingerprint="context-v1",
            )
    caps.create.assert_called_once()
    caps.delete.assert_called_once_with(spec.asset_id)


def test_detail_review_includes_nonrequired_populated_attributes(qtbot):
    dialog = CAPDetailReviewDialog(_spec())
    qtbot.addWidget(dialog)
    names = {field for field, _value, _choice, _evidence in dialog.rows}
    assert "architecture" in names
    assert "materials" in names
    assert {"layout", "scale", "spatial_anchors", "lighting"}.issubset(names)
    assert all(choice.currentData() is DetailDecision.DEFER for _, _, choice, _ in dialog.rows)
