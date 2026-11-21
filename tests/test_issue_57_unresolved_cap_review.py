"""Issue #57: all Reject/Defer is a durable review, never an empty CAP."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError
from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.context_preparation import CAPContextManifest, CAPContextSource
from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DesignReviewPackage,
    DetailDecision,
    DetailOrigin,
    apply_review,
    reviewed_canonical_attributes,
)
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.story_batch import StoryBatchError
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.application.caps.unresolved_design_reviews import (
    UnresolvedCAPReviewLedger,
    UnresolvedCAPReviewRecord,
)
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.dialogs.cap_detail_review_dialog import CAPDetailReviewDialog


def _spec() -> CAPStructuredSpecification:
    return CAPStructuredSpecification(
        asset_id="CAP-TEC-001",
        category=AssetCategory.TECHNOLOGY,
        design_intent="Unverified automated inspection system proposal",
        canonical_attributes={
            "geometry": "Unverified wheeled inspection robot",
            "materials": "Unverified shell",
            "components": "Camera module",
            "operating_states": "Patrol",
        },
        master_prompt="Unapproved candidate only",
        origin="story_intelligence_proposal",
    )


def _review(
    spec: CAPStructuredSpecification,
    decisions: dict[str, DetailDecision],
) -> DesignReviewPackage:
    return DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        reviewer="Operator",
        story_fingerprint="story-current",
        context_fingerprint="context-current",
        fields=tuple(
            DesignFieldReview(
                field=field,
                proposed_value=value,
                final_value=value if decisions[field] is DetailDecision.ACCEPT else "",
                decision=decisions[field],
                origin=DetailOrigin.DESIGN_PROPOSAL,
                evidence=f"Reviewed {field} against governed Shot",
                rationale="Not physical canon",
            )
            for field, value in spec.canonical_attributes.items()
        ),
    )


def _manifest(spec: CAPStructuredSpecification) -> CAPContextManifest:
    return CAPContextManifest(
        story_id="STORY-001",
        asset_id=spec.asset_id,
        story_fingerprint="story-current",
        asset_fingerprint="asset-current",
        fingerprint="context-current",
        sources=(
            CAPContextSource(
                "approved_story",
                "STORY-001",
                "description",
                "An empty engineering bay aboard the vessel",
                "approved_story",
                "story-source-sha",
            ),
            CAPContextSource(
                "governed_shot",
                "EP-001-SCN-001-SHT-001",
                "action",
                "The camera viewpoint advances toward the console",
                "unverified_shot",
                "shot-source-sha",
            ),
        ),
        warnings=("Draft Shot text is not approved Story Canon",),
    )


def _service(tmp_path, spec):
    caps = Mock()
    caps.get.side_effect = CAPNotFoundError("CAP is missing")
    caps.assets.get.return_value = SimpleNamespace(
        asset_id=spec.asset_id, name="Inspection camera", category=spec.category
    )
    caps.assets.projects.project_directory = tmp_path
    specifications = Mock()
    specifications.get.return_value = None
    specifications.caps = caps
    batch = Mock()
    batch.current_story_fingerprint.return_value = "story-current"
    batch.generator.specifications = specifications
    batch.generator.generator.assets.projects.project_directory = tmp_path
    service = StoryCAPBatchReviewService(batch)
    service.prepare_context = Mock(return_value=_manifest(spec))
    service.validate_reviewed_dependencies = Mock(return_value=())
    return service, caps


@pytest.mark.parametrize(
    "decisions",
    [
        (DetailDecision.REJECT,) * 4,
        (DetailDecision.DEFER,) * 4,
        (DetailDecision.DEFER, DetailDecision.DEFER, DetailDecision.REJECT, DetailDecision.REJECT),
    ],
    ids=["all_reject", "all_defer", "mixed_no_accept"],
)
def test_review_only_saves_no_cap_and_round_trips_every_decision(tmp_path, decisions):
    spec = _spec()
    review = _review(spec, dict(zip(spec.canonical_attributes, decisions, strict=True)))
    service, caps = _service(tmp_path, spec)
    protected = tmp_path / "planning" / "asset_resolutions.json"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"Original governed binding bytes; do not rewrite")
    cached = tmp_path / "production" / "caps" / "proposal_cache" / "existing.json"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"Original cached paid proposal bytes; do not rewrite")

    outcome = service.save_reviewed(
        "STORY-001",
        spec,
        "story-current",
        review,
        expected_context_fingerprint="context-current",
    )
    assert outcome.outcome == "no_eligible_attributes"
    assert outcome.record_id
    caps.create.assert_not_called()
    caps.update.assert_not_called()
    caps.delete.assert_not_called()
    assert protected.read_bytes() == b"Original governed binding bytes; do not rewrite"
    assert cached.read_bytes() == b"Original cached paid proposal bytes; do not rewrite"
    service.batch.generator.generator.generate.assert_not_called()
    service.validate_reviewed_dependencies.assert_not_called()
    assert service.batch.generator.specifications.get(spec.asset_id) is None

    restored = UnresolvedCAPReviewLedger(tmp_path).latest("STORY-001", spec.asset_id)
    assert restored is not None
    assert restored.outcome == "no_eligible_attributes"
    assert restored.review == review
    assert restored.specification_snapshot == spec
    assert restored.reviewed_at_utc
    assert restored.context_sources[0].fingerprint == "story-source-sha"
    assert restored.context_sources[1].excerpt.startswith("The camera")
    assert restored.context_warnings == ("Draft Shot text is not approved Story Canon",)
    assert restored.canon_approved is False and restored.production_ready is False

    # Repeated Save is idempotent, retaining exactly one immutable record.
    assert (
        service.save_reviewed(
            "STORY-001",
            spec,
            "story-current",
            review,
            expected_context_fingerprint="context-current",
        ).record_id
        == outcome.record_id
    )
    assert len(service.unresolved_reviews("STORY-001", spec.asset_id)) == 1
    assert len(list((tmp_path / "production" / "caps" / "review_decisions").rglob("*.json"))) == 1


def test_one_accepted_attribute_still_uses_nonempty_cap_contract(tmp_path):
    spec = _spec()
    decisions = dict.fromkeys(spec.canonical_attributes, DetailDecision.REJECT)
    decisions["geometry"] = DetailDecision.ACCEPT
    review = _review(spec, decisions)
    assert reviewed_canonical_attributes(spec, review) == {
        "geometry": spec.canonical_attributes["geometry"]
    }
    updated, audit = apply_review(spec, review)
    assert updated.canonical_attributes == {"geometry": spec.canonical_attributes["geometry"]}
    assert json.loads(audit)["canon_approved"] is False
    with pytest.raises(ValidationError, match="canonical_attributes"):
        CAPStructuredSpecification.model_validate({**spec.model_dump(), "canonical_attributes": {}})
    with pytest.raises(ValueError, match="Accepted or edited"):
        UnresolvedCAPReviewLedger(tmp_path).save(spec, review, _manifest(spec))


@pytest.mark.parametrize("stale", ["story", "context", "asset"])
def test_stale_context_or_asset_blocks_review_only_without_file_or_cap(tmp_path, stale):
    spec = _spec()
    review = _review(spec, dict.fromkeys(spec.canonical_attributes, DetailDecision.DEFER))
    service, caps = _service(tmp_path, spec)
    if stale == "story":
        service.batch.current_story_fingerprint.return_value = "different-story"
    elif stale == "context":
        original = _manifest(spec)
        service.prepare_context.return_value = CAPContextManifest(
            **{**original.__dict__, "fingerprint": "different-context"}
        )
    else:
        caps.assets.get.return_value.category = AssetCategory.PROP

    with pytest.raises(StoryBatchError, match=r"Story changed|context changed|Asset category"):
        service.save_reviewed(
            "STORY-001",
            spec,
            "story-current",
            review,
            expected_context_fingerprint="context-current",
        )
    assert not (tmp_path / "production").exists()
    caps.create.assert_not_called()
    caps.update.assert_not_called()


def test_corrupt_or_fabricated_approval_record_is_not_reopened(tmp_path):
    spec = _spec()
    review = _review(spec, dict.fromkeys(spec.canonical_attributes, DetailDecision.REJECT))
    ledger = UnresolvedCAPReviewLedger(tmp_path)
    record = ledger.save(spec, review, _manifest(spec))
    with pytest.raises(ValidationError):
        UnresolvedCAPReviewRecord.model_validate({**record.model_dump(), "canon_approved": True})
    with pytest.raises(ValidationError):
        UnresolvedCAPReviewRecord.model_validate({**record.model_dump(), "outcome": "draft_cap"})
    with pytest.raises(ValidationError):
        UnresolvedCAPReviewRecord.model_validate(
            {**record.model_dump(), "asset_fingerprint": "tampered"}
        )
    entry = next(ledger.directory.rglob("*.json"))
    entry.write_text("{corrupt", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid"):
        ledger.list_records("STORY-001", spec.asset_id)


def test_reopened_review_can_be_reclassified_without_paying_or_overwriting(tmp_path):
    spec = _spec()
    ledger = UnresolvedCAPReviewLedger(tmp_path)
    all_defer = _review(spec, dict.fromkeys(spec.canonical_attributes, DetailDecision.DEFER))
    original = ledger.save(spec, all_defer, _manifest(spec))
    revised = _review(spec, dict.fromkeys(spec.canonical_attributes, DetailDecision.REJECT))
    ledger.save(spec, revised, _manifest(spec))
    records = ledger.list_records("STORY-001", spec.asset_id)
    assert len(records) == 2
    assert {item.record_id for item in records} == {
        original.record_id,
        ledger.latest("STORY-001", spec.asset_id).record_id,
    }
    assert {item.review.fields[0].decision for item in records} == {
        DetailDecision.DEFER,
        DetailDecision.REJECT,
    }


def test_qt_zero_eligible_decision_accept_and_offline_reopen(qtbot, tmp_path):
    spec = _spec()
    original = _review(spec, dict.fromkeys(spec.canonical_attributes, DetailDecision.REJECT))
    saved = UnresolvedCAPReviewLedger(tmp_path).save(spec, original, _manifest(spec))
    dialog = CAPDetailReviewDialog(spec, previous_review=saved.review)
    qtbot.addWidget(dialog)
    assert {choice.currentData() for _, _, choice, _ in dialog.rows} == {DetailDecision.REJECT}
    assert all("Reviewed" in evidence.toPlainText() for _, _, _, evidence in dialog.rows)
    with patch.object(QMessageBox, "warning") as warnings:
        dialog._accept_review()
    warnings.assert_not_called()
    assert dialog.reviewed() == original.model_copy(
        update={"story_fingerprint": "", "context_fingerprint": ""}
    )
    with pytest.raises(ValueError, match="stale"):
        CAPDetailReviewDialog(
            spec.model_copy(update={"design_intent": "different"}), previous_review=saved.review
        )
