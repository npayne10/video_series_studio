"""Issue #54: current approved-Story candidates for already-specified Draft CAPs."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.context_preparation import CAPContextManifest, CAPContextSource
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
    prepare_story_field_revisions,
    save_draft_cap_field_revision,
)
from vscs.application.caps.story_field_grounding import CAPFieldOrigin
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus
from vscs.presentation.dialogs.edit_existing_draft_cap_dialog import EditExistingDraftCAPDialog

APPROVED_STORY = (
    "The diagnostic console has an upright rectangular housing made of matte "
    "graphite-coated metal. Its front face contains one broad cobalt-blue display. "
    "Directly below the display is a shallow control shelf carrying exactly three "
    "small circular buttons in a straight row. A rotary dial sits to their right "
    "in a recess. The dial remains below the shelf plane. "
    "Vertical ribbed grip panels extend along the sides. "
    "The nearby maintenance workstation is physically separate."
)


def _harness(*, source=APPROVED_STORY, extra_shot=""):
    spec = CAPStructuredSpecification(
        asset_id="CAP-PRP-002",
        category=AssetCategory.PROP,
        design_intent="Diagnostic console (unapproved physical design)",
        canonical_attributes={"geometry": "Previously accepted upright rectangular console"},
        master_prompt="Draft only",
    )
    review = DesignReviewPackage(
        asset_id=spec.asset_id,
        base_fingerprint=spec.fingerprint(),
        fields=(
            DesignFieldReview(
                field="geometry",
                proposed_value="Previously accepted upright rectangular console",
                final_value="Previously accepted upright rectangular console",
                decision=DetailDecision.ACCEPT,
                origin=DetailOrigin.DESIGN_PROPOSAL,
                evidence="Original human geometry decision",
            ),
            DesignFieldReview(
                field="materials",
                proposed_value="AI suggested unverified aluminium shell",
                decision=DetailDecision.DEFER,
                origin=DetailOrigin.DESIGN_PROPOSAL,
            ),
            DesignFieldReview(
                field="components",
                proposed_value="AI suggested extra moving hardware",
                decision=DetailDecision.REJECT,
                origin=DetailOrigin.DESIGN_PROPOSAL,
            ),
            DesignFieldReview(
                field="scale",
                proposed_value="Invented 1.2 m high",
                decision=DetailDecision.DEFER,
                origin=DetailOrigin.DESIGN_PROPOSAL,
            ),
        ),
        reviewer="Earlier operator",
        story_fingerprint="story-current",
        context_fingerprint="context-current",
    )
    reviewed, audit = apply_review(spec, review)
    reviewed = reviewed.model_copy(
        update={"master_prompt": build_reviewed_master_prompt(reviewed, review)}
    )
    metadata = {
        SPECIFICATION_METADATA_KEY: json.dumps(reviewed.model_dump(mode="json")),
        DESIGN_REVIEW_KEY: audit,
        "other_metadata": "preserve exactly",
    }
    cap = SimpleNamespace(
        asset_id=spec.asset_id, status=CAPStatus.DRAFT, production_metadata=metadata
    )
    asset = SimpleNamespace(
        asset_id=spec.asset_id,
        name="Diagnostic console",
        category=AssetCategory.PROP,
    )
    sources = (
        CAPContextSource(
            "approved_story",
            "STORY-001",
            "source_text",
            source,
            "approved_story_context",
            "source-sha-54",
        ),
    )
    if extra_shot:
        sources += (
            CAPContextSource(
                "governed_shot",
                "EP-001-SCN-001-SHT-001",
                "shot_constraints",
                extra_shot,
                "verified_ready_shot",
                "shot-sha-54",
            ),
        )
    context = CAPContextManifest(
        story_id="STORY-001",
        asset_id=spec.asset_id,
        story_fingerprint="story-current",
        asset_fingerprint="asset-current",
        sources=sources,
        warnings=(),
        fingerprint="context-current",
    )
    repo = SimpleNamespace(compare_and_swap_draft_metadata=Mock())
    caps = SimpleNamespace(
        get=Mock(return_value=cap),
        assets=SimpleNamespace(get=Mock(return_value=asset)),
        repository=repo,
    )
    service = SimpleNamespace(
        batch=SimpleNamespace(
            current_story_fingerprint=Mock(return_value="story-current"),
            generator=SimpleNamespace(specifications=SimpleNamespace(caps=caps)),
        ),
        discover=Mock(
            return_value=(
                SimpleNamespace(asset_id=spec.asset_id, has_cap=True, has_specification=True),
            )
        ),
        prepare_context=Mock(return_value=context),
        validate_reviewed_dependencies=Mock(return_value=()),
    )
    snapshot = prepare_draft_cap_revision(service, "STORY-001", spec.asset_id)
    return service, snapshot, cap, repo


def test_existing_draft_offline_story_candidates_target_only_deferred_or_rejected_fields():
    service, snapshot, _cap, repo = _harness()
    candidates = prepare_story_field_revisions(service, snapshot)
    assert {candidate.field for candidate in candidates} == {"materials", "components"}
    assert all(candidate.origin is CAPFieldOrigin.STORY_CANDIDATE for candidate in candidates)
    assert all(candidate.source_fingerprint == "source-sha-54" for candidate in candidates)
    assert all(candidate.context_fingerprint == "context-current" for candidate in candidates)
    assert "matte graphite-coated metal" in candidates[0].value
    assert "exactly three small circular buttons" in candidates[1].value
    assert "dial remains below the shelf plane" in candidates[1].value
    assert snapshot.specification.canonical_attributes == {
        "geometry": "Previously accepted upright rectangular console"
    }
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_offline_existing_draft_review_preserves_accepted_fields_and_audits_source():
    service, snapshot, cap, repo = _harness()
    original = snapshot.review.fields[0].model_dump(mode="json")
    candidate = next(
        item
        for item in prepare_story_field_revisions(service, snapshot)
        if item.field == "materials"
    )
    saved = save_draft_cap_field_revision(
        service,
        snapshot,
        field="materials",
        reviewed_value=candidate.value,
        rationale="Human verified the shell material belongs to the console",
        reviewer="Neill",
        story_provenance=candidate,
    )
    assert (
        saved.canonical_attributes["geometry"]
        == snapshot.specification.canonical_attributes["geometry"]
    )
    assert "matte graphite-coated metal" in saved.canonical_attributes["materials"]
    assert "components" not in saved.canonical_attributes
    repo.compare_and_swap_draft_metadata.assert_called_once()
    expected = repo.compare_and_swap_draft_metadata.call_args.kwargs
    assert expected["expected"] == cap.production_metadata
    new_metadata = expected["replacement"]
    assert new_metadata["other_metadata"] == "preserve exactly"
    decisions = json.loads(new_metadata[DESIGN_REVIEW_KEY])["fields"]
    assert decisions[0] == original
    assert decisions[1]["origin"] == DetailOrigin.STORY_CANDIDATE.value
    assert decisions[1]["source_record_id"] == "STORY-001"
    assert decisions[1]["source_field"] == "source_text"
    assert decisions[1]["source_fingerprint"] == "source-sha-54"
    assert decisions[1]["decision"] == "edit"
    assert decisions[2]["decision"] == "reject"
    assert decisions[3]["decision"] == "defer"
    history = json.loads(new_metadata[REVISION_HISTORY_KEY])
    assert history[0]["source_fingerprint"] == "source-sha-54"
    assert history[0]["prior_decision"] == "defer"
    assert json.loads(history[0]["prior_review_audit"])["reviewer"] == "Earlier operator"
    assert json.loads(new_metadata[DESIGN_REVIEW_KEY])["canon_approved"] is False


def test_reopen_after_one_story_field_can_review_second_without_overwriting_first():
    service, first, cap, repo = _harness()

    def commit(_asset_id, *, expected, replacement):
        assert cap.production_metadata == expected
        cap.production_metadata = replacement

    repo.compare_and_swap_draft_metadata.side_effect = commit
    material = next(
        item for item in prepare_story_field_revisions(service, first) if item.field == "materials"
    )
    save_draft_cap_field_revision(
        service,
        first,
        field="materials",
        reviewed_value=material.value,
        rationale="Verified original Story material",
        reviewer="Neill",
        story_provenance=material,
    )
    second = prepare_draft_cap_revision(service, "STORY-001", cap.asset_id)
    assert {item.field for item in prepare_story_field_revisions(service, second)} == {"components"}
    parts = prepare_story_field_revisions(service, second)[0]
    final = save_draft_cap_field_revision(
        service,
        second,
        field="components",
        reviewed_value=parts.value,
        rationale="Verified original Story controls and dial clearance",
        reviewer="Neill",
        story_provenance=parts,
    )
    assert (
        final.canonical_attributes["geometry"]
        == first.specification.canonical_attributes["geometry"]
    )
    assert final.canonical_attributes["materials"] == material.value
    assert final.canonical_attributes["components"] == parts.value
    assert "scale" not in final.canonical_attributes
    history = json.loads(cap.production_metadata[REVISION_HISTORY_KEY])
    assert [item["field"] for item in history] == ["materials", "components"]
    decisions = json.loads(cap.production_metadata[DESIGN_REVIEW_KEY])["fields"]
    assert decisions[0]["evidence"] == "Original human geometry decision"
    assert decisions[1]["source_fingerprint"] == "source-sha-54"
    assert decisions[2]["source_fingerprint"] == "source-sha-54"
    assert decisions[3]["decision"] == "defer"


@pytest.mark.parametrize("tamper", ["field", "value", "sha", "origin"])
def test_forged_or_modified_source_provenance_fails_without_draft_write(tamper):
    service, snapshot, _cap, repo = _harness()
    candidate = next(
        item
        for item in prepare_story_field_revisions(service, snapshot)
        if item.field == "materials"
    )
    alteration = {
        "field": {"field": "scale"},
        "value": {"value": "Proposed 1.2 m aluminium shell"},
        "sha": {"source_fingerprint": "forged"},
        "origin": {"origin": CAPFieldOrigin.MODEL_PROPOSAL},
    }[tamper]
    forged = candidate.model_copy(update=alteration)
    with pytest.raises(DraftCAPRevisionError, match=r"unsupported|changed"):
        save_draft_cap_field_revision(
            service,
            snapshot,
            field="materials",
            reviewed_value=candidate.value,
            rationale="Attempted unverified reuse",
            reviewer="Operator",
            story_provenance=forged,
        )
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_source_revised_after_inspection_cannot_be_saved():
    service, snapshot, cap, repo = _harness()
    candidate = next(
        item
        for item in prepare_story_field_revisions(service, snapshot)
        if item.field == "materials"
    )
    service.batch.current_story_fingerprint.return_value = "story-changed"
    with pytest.raises(DraftCAPRevisionError, match="Story changed"):
        save_draft_cap_field_revision(
            service,
            snapshot,
            field="materials",
            reviewed_value=candidate.value,
            rationale="Original source was current before change",
            reviewer="Operator",
            story_provenance=candidate,
        )
    assert cap.status is CAPStatus.DRAFT
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_source_text_changed_with_same_context_label_still_fails_equality_check():
    service, snapshot, _cap, repo = _harness()
    original = next(
        item
        for item in prepare_story_field_revisions(service, snapshot)
        if item.field == "materials"
    )
    altered, _, _, _ = _harness(
        source=APPROVED_STORY.replace("graphite-coated metal", "powder-coated aluminium")
    )
    service.prepare_context.return_value = altered.prepare_context.return_value
    with pytest.raises(DraftCAPRevisionError, match=r"unsupported|changed"):
        save_draft_cap_field_revision(
            service,
            snapshot,
            field="materials",
            reviewed_value=original.value,
            rationale="Stale sourced material",
            reviewer="Operator",
            story_provenance=original,
        )
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_story_candidates_cannot_override_previously_accepted_geometry():
    service, snapshot, _cap, repo = _harness()
    assert "geometry" not in {
        item.field for item in prepare_story_field_revisions(service, snapshot)
    }
    with pytest.raises(DraftCAPRevisionError, match="deferred/rejected"):
        save_draft_cap_field_revision(
            service,
            snapshot,
            field="geometry",
            reviewed_value="Replacement geometry",
            rationale="Invalid replacement",
            reviewer="Operator",
        )
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_shot_only_materials_never_become_existing_draft_story_candidates():
    service, snapshot, _cap, _repo = _harness(
        source="The diagnostic console stands apart from the workstation.",
        extra_shot="The diagnostic console has a titanium casing and metal wheels.",
    )
    assert prepare_story_field_revisions(service, snapshot) == ()


def test_existing_draft_story_button_loads_without_paid_calls_or_draft_mutation(qtbot):
    service, snapshot, _cap, repo = _harness()
    dialog = EditExistingDraftCAPDialog(service, snapshot)
    qtbot.addWidget(dialog)
    assert dialog.accepted_view.isReadOnly()
    assert "geometry:" in dialog.accepted_view.toPlainText()
    assert dialog.field.count() == 3
    assert dialog.field.findData("geometry") == -1
    dialog.load_story_button.click()
    assert "matte graphite-coated metal" in dialog.value.toPlainText()
    assert "STORY-001.source_text" in dialog.rationale.toPlainText()
    assert "source-sha-54" in dialog.rationale.toPlainText()
    assert dialog.value.isReadOnly()
    assert dialog.save_button is not None and dialog.save_button.isEnabled()
    assert dialog._proposal is None and dialog._request is None
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_existing_draft_requires_reason_and_confirmation_before_story_save(qtbot):
    service, snapshot, _cap, repo = _harness()
    dialog = EditExistingDraftCAPDialog(service, snapshot)
    qtbot.addWidget(dialog)
    dialog.load_story_button.click()
    with (
        patch.object(QMessageBox, "warning") as warnings,
        patch.object(QMessageBox, "question") as question,
    ):
        dialog._save()
    warnings.assert_called_once()
    question.assert_not_called()
    repo.compare_and_swap_draft_metadata.assert_not_called()

    dialog.operator_reason.setPlainText("Confirmed material refers to console shell")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog._save()
    repo.compare_and_swap_draft_metadata.assert_not_called()

    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "information") as notice,
    ):
        dialog._save()
    repo.compare_and_swap_draft_metadata.assert_called_once()
    notice.assert_called_once()


def test_switching_fields_discards_previous_review_selection_and_reason(qtbot):
    service, snapshot, _cap, repo = _harness()
    dialog = EditExistingDraftCAPDialog(service, snapshot)
    qtbot.addWidget(dialog)
    dialog.load_story_button.click()
    dialog.operator_reason.setPlainText("Review for materials")
    dialog.field.setCurrentIndex(dialog.field.findData("components"))
    assert not dialog.save_button.isEnabled()
    assert dialog.value.toPlainText() == ""
    assert dialog.operator_reason.toPlainText() == ""
    dialog.load_story_button.click()
    assert "cobalt-blue display" in dialog.value.toPlainText()
    repo.compare_and_swap_draft_metadata.assert_not_called()


def test_unsupported_existing_draft_field_never_enables_save_or_ai(qtbot):
    service, snapshot, _cap, repo = _harness()
    dialog = EditExistingDraftCAPDialog(service, snapshot)
    qtbot.addWidget(dialog)
    dialog.field.setCurrentIndex(dialog.field.findData("scale"))
    dialog.load_story_button.click()
    assert "No approved-Story candidate" in dialog.proposal_status.text()
    assert not dialog.save_button.isEnabled()
    repo.compare_and_swap_draft_metadata.assert_not_called()
