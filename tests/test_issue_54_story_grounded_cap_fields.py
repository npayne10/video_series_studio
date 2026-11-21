"""Issue #54: offline Story-grounded CAP normalization and provenance gates."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.context_preparation import CAPContextManifest, CAPContextSource
from vscs.application.caps.design_completion import (
    DetailDecision,
    DetailOrigin,
    apply_review,
)
from vscs.application.caps.provider_design_expansion import ProposedDesignField
from vscs.application.caps.story_field_grounding import (
    CAPFieldOrigin,
    reconcile_grounded_fields,
)
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs.cap_detail_review_dialog import CAPDetailReviewDialog
from vscs.presentation.dialogs.story_cap_specification_dialog import StoryCAPSpecificationDialog

STORY = (
    "An unoccupied engineering inspection bay aboard a deep-space survey vessel "
    "has neutral grey panels and diffuse overhead utility lighting. "
    "A compact maintenance workstation stands to one side. "
    "Beside it, clearly separate, stands a freestanding diagnostic console.\n\n"
    "The diagnostic console has an upright rectangular housing made of matte "
    "graphite-coated metal. Its front face contains one broad cobalt-blue display. "
    "Directly below the display is a shallow horizontal control shelf carrying "
    "exactly three small circular buttons in a straight row. "
    "To the right of the buttons sits one rotary control dial inside a circular recess. "
    "The dial's outermost surface remains below the shelf plane. "
    "Vertical ribbed grip panels extend along both sides of the console housing. "
    "No lettering, brands, logos, extra screens or additional controls are visible."
)


def _asset(asset_id="CAP-PRP-002", name="Diagnostic console", category=AssetCategory.PROP):
    return Asset.model_construct(
        asset_id=asset_id,
        name=name,
        category=category,
        description=f"Unapproved registered {name}",
    )


def _spec(asset):
    key = {
        AssetCategory.PROP: "geometry",
        AssetCategory.LOCATION: "architecture",
        AssetCategory.SHIP: "silhouette",
    }[asset.category]
    return CAPStructuredSpecification(
        asset_id=asset.asset_id,
        category=asset.category,
        design_intent=f"Advisory {asset.name}",
        canonical_attributes={key: f"Model-proposed {asset.name} silhouette and identity"},
        master_prompt="Unapproved provider reference proposal",
        origin="story_intelligence_proposal",
    )


def _manifest(asset, *, source=STORY, shot_authority="unverified_shot", shot_text=""):
    sources = (
        CAPContextSource(
            "approved_story",
            "STORY-001",
            "source_text",
            source,
            "approved_story_context",
            "story-sha-001",
        ),
    ) + (
        (
            CAPContextSource(
                "governed_shot",
                "EP-001-SCN-001-SHT-001",
                "shot_constraints",
                shot_text,
                shot_authority,
                "shot-sha-002",
            ),
        )
        if shot_text
        else ()
    )
    return CAPContextManifest(
        story_id="STORY-001",
        asset_id=asset.asset_id,
        story_fingerprint="story-rev-007",
        asset_fingerprint="asset-sha-003",
        sources=sources,
        warnings=("Draft Shot evidence is unverified",),
        fingerprint="story-shot-context-sha-004",
    )


def _suggestion(field, value):
    return ProposedDesignField(field=field, proposed_value=value, rationale="AI design only")


def test_console_materials_and_components_are_autofilled_from_source_not_ai():
    asset = _asset()
    draft = _spec(asset)
    alternatives = (
        _suggestion("materials", "Proposed anodized aluminium housing and wheel treads"),
        _suggestion("components", "Proposed self-propelled robot and motorized wheels"),
        _suggestion("scale", "Proposed 1.2 m height and 0.42 m depth"),
    )
    updated, evidence, issues = reconcile_grounded_fields(
        draft, asset.name, _manifest(asset), alternatives
    )
    assert updated.canonical_attributes["geometry"] == draft.canonical_attributes["geometry"]
    assert "matte graphite-coated metal" in updated.canonical_attributes["materials"]
    assert "one broad cobalt-blue display" in updated.canonical_attributes["components"]
    assert "exactly three small circular buttons" in updated.canonical_attributes["components"]
    assert (
        "No lettering, brands, logos, extra screens" in updated.canonical_attributes["components"]
    )
    # The dial's clearance is an important physical constraint from Story.
    assert (
        "outermost surface remains below the shelf plane"
        in updated.canonical_attributes["components"]
    )
    assert "scale" not in updated.canonical_attributes
    assert "1.2 m" not in str(updated.canonical_attributes)
    by_field = {item.field: item for item in evidence}
    for field in ("materials", "components"):
        assert by_field[field].origin is CAPFieldOrigin.STORY_CANDIDATE
        assert by_field[field].source_field == "source_text"
        assert by_field[field].source_fingerprint == "story-sha-001"
        assert by_field[field].context_fingerprint == "story-shot-context-sha-004"
        assert by_field[field].value in by_field[field].excerpt
    assert by_field["scale"].origin is CAPFieldOrigin.MODEL_PROPOSAL
    assert any(issue.code == "unsourced_measurement" for issue in issues)


def test_location_layout_and_lighting_not_unsupported_scale_or_room_materials():
    asset = _asset("CAP-LOC-001", "Engineering inspection bay", AssetCategory.LOCATION)
    updated, evidence, issues = reconcile_grounded_fields(
        _spec(asset),
        asset.name,
        _manifest(asset),
        (
            _suggestion("layout", "Proposed centred doorway and service chase"),
            _suggestion("lighting", "Proposed two rows of overhead fixtures"),
            _suggestion("scale", "Proposed room 6.0 m long by 4.0 m wide"),
            _suggestion("materials", "Proposed low-sheen metal walls and floor"),
        ),
    )
    assert "engineering inspection bay" in updated.canonical_attributes["layout"]
    assert "diffuse overhead utility lighting" in updated.canonical_attributes["lighting"]
    assert "architecture" in updated.canonical_attributes
    assert not {"scale", "materials", "spatial_anchors"} & updated.canonical_attributes.keys()
    assert "doorway" not in str(updated.canonical_attributes)
    assert "two rows" not in str(updated.canonical_attributes)
    assert {item.field: item.origin for item in evidence}[
        "lighting"
    ] is CAPFieldOrigin.STORY_CANDIDATE
    assert any(item.code == "unsourced_measurement" for item in issues)


def test_ship_dimensions_never_inherit_contained_bay_dimensions():
    asset = _asset("CAP-SHP-001", "Deep-space survey vessel", AssetCategory.SHIP)
    source = (
        "The deep-space survey vessel contains an engineering inspection bay. "
        "The engineering inspection bay is 6.0 m long, 4.0 m wide and 2.7 m high."
    )
    updated, evidence, issues = reconcile_grounded_fields(
        _spec(asset),
        asset.name,
        _manifest(asset, source=source),
        (_suggestion("dimensions", "Proposed engineering bay 8.0 m by 6.0 m by 3.5 m"),),
    )
    assert "dimensions" not in updated.canonical_attributes
    assert {item.field: item.origin for item in evidence}[
        "dimensions"
    ] is CAPFieldOrigin.MODEL_PROPOSAL
    assert "contained_asset_scope" in {item.code for item in issues}
    assert "unsourced_measurement" in {item.code for item in issues}


def test_workstation_does_not_inherit_consoles_graphite_or_controls():
    asset = _asset("CAP-PRP-001", "Maintenance workstation")
    updated, evidence, _ = reconcile_grounded_fields(_spec(asset), asset.name, _manifest(asset), ())
    assert "materials" not in updated.canonical_attributes
    assert "components" not in updated.canonical_attributes
    assert "matte graphite" not in str(updated.canonical_attributes)
    assert {item.field: item.origin for item in evidence}["materials"] is CAPFieldOrigin.UNRESOLVED


def test_shared_paragraph_never_transfers_neighbour_materials_or_components():
    asset = _asset()
    source = (
        "The maintenance workstation has a powder-coated steel frame and four legs. "
        "The diagnostic console stands nearby. "
        "Its front face includes a single cobalt-blue display. "
        "The maintenance workstation has rubber feet and an open lower shelf."
    )
    updated, _, _ = reconcile_grounded_fields(
        _spec(asset), asset.name, _manifest(asset, source=source), ()
    )
    assert "materials" not in updated.canonical_attributes
    assert "single cobalt-blue display" in updated.canonical_attributes["components"]
    assert "rubber feet" not in updated.canonical_attributes["components"]
    assert "open lower shelf" not in updated.canonical_attributes["components"]


def test_numeric_scale_elsewhere_in_story_cannot_validate_console_scale():
    asset = _asset()
    source = (
        "The maintenance workstation is 0.80 m wide and 0.90 m high. "
        "The diagnostic console has one broad display and three buttons."
    )
    updated, _, issues = reconcile_grounded_fields(
        _spec(asset),
        asset.name,
        _manifest(asset, source=source),
        (_suggestion("scale", "Proposed console 0.80 m wide"),),
    )
    assert "scale" not in updated.canonical_attributes
    assert "unsourced_measurement" in {issue.code for issue in issues}


@pytest.mark.parametrize("shot_authority", ["unverified_shot", "verified_ready_shot"])
def test_shot_only_material_never_fills_story_physical_fact(shot_authority):
    asset = _asset()
    shot = "The diagnostic console has a bright orange titanium-alloy casing."
    approved = "The diagnostic console is freestanding."
    updated, evidence, _ = reconcile_grounded_fields(
        _spec(asset),
        asset.name,
        _manifest(asset, source=approved, shot_authority=shot_authority, shot_text=shot),
        (_suggestion("materials", "Proposed titanium-alloy casing"),),
    )
    assert "materials" not in updated.canonical_attributes
    provenance = next(item for item in evidence if item.field == "materials")
    assert provenance.origin is CAPFieldOrigin.MODEL_PROPOSAL
    assert provenance.shot_authority == shot_authority
    assert provenance.shot_fingerprint == "shot-sha-002"
    assert "titanium-alloy" in provenance.shot_excerpt


def test_legacy_cache_is_enriched_and_round_trips_no_extra_provider_call():
    asset = _asset()
    original = StoryCAPProposal(_spec(asset), "geometry", ("Unapproved",))
    cache = original.to_cache()
    assert cache["field_provenance"] == []
    cache.pop("field_provenance")  # Existing v2 persisted proposal before Issue #54.
    loaded = StoryCAPProposal.from_cache(cache)
    enriched = loaded.ground_against_story(asset, _manifest(asset))
    assert "materials" in enriched.specification.canonical_attributes
    assert "components" in enriched.specification.canonical_attributes
    restored = StoryCAPProposal.from_cache(enriched.to_cache())
    assert restored.field_provenance == enriched.field_provenance
    assert restored.specification == enriched.specification


def test_operator_edit_is_recorded_not_relabelled_story_fact():
    asset = _asset()
    grounded = StoryCAPProposal(_spec(asset), "geometry", ()).ground_against_story(
        asset, _manifest(asset)
    )
    edited = grounded.specification.model_copy(
        update={
            "canonical_attributes": {
                **grounded.specification.canonical_attributes,
                "materials": "Operator-created alternative to graphite-coated metal",
            }
        }
    )
    reviewed = grounded.with_operator_edits(edited)
    status = {item.field: item for item in reviewed.field_provenance}
    assert status["materials"].origin is CAPFieldOrigin.OPERATOR_EDITED
    assert status["materials"].source_fingerprint == "story-sha-001"
    assert "graphite-coated" in status["materials"].excerpt
    assert status["components"].origin is CAPFieldOrigin.STORY_CANDIDATE
    again = reviewed.ground_against_story(asset, _manifest(asset))
    assert (
        again.specification.canonical_attributes["materials"]
        == edited.canonical_attributes["materials"]
    )
    assert {item.field: item.origin for item in again.field_provenance}[
        "materials"
    ] is CAPFieldOrigin.OPERATOR_EDITED


def test_asset_identity_and_fingerprint_fail_closed_without_writes(tmp_path):
    asset = _asset()
    wrong = _asset("CAP-LOC-999", "Wrong asset", AssetCategory.LOCATION)
    with pytest.raises(ValueError, match="does not match"):
        reconcile_grounded_fields(_spec(asset), asset.name, _manifest(wrong), ())
    assert not list(tmp_path.iterdir())


def test_qt_shows_source_provenance_and_requires_explicit_group_review(qtbot):
    asset = _asset()
    grounded = StoryCAPProposal(
        _spec(asset),
        "geometry",
        (),
        design_suggestions=(_suggestion("scale", "Proposed 1.2 m tall"),),
    ).ground_against_story(asset, _manifest(asset))
    initial = StoryCAPSpecificationDialog(grounded)
    qtbot.addWidget(initial)
    summary = initial.detail_evidence.toPlainText()
    assert "approved_story_candidate" in summary
    assert "story-sha-001" in summary
    assert "AI scale:" in summary

    dialog = CAPDetailReviewDialog(
        grounded.specification,
        suggestions=grounded.design_suggestions,
        field_provenance=grounded.field_provenance,
    )
    qtbot.addWidget(dialog)
    assert all(choice.currentData() == DetailDecision.DEFER for _, _, choice, _ in dialog.rows)
    with pytest.raises(ValueError, match="No accepted review"):
        dialog.reviewed()  # No implicit approval from a provenance label.
    dialog.apply_source_suggestions.click()
    choices = {field: choice.currentData() for field, _, choice, _ in dialog.rows}
    assert choices["materials"] == DetailDecision.ACCEPT
    assert choices["components"] == DetailDecision.ACCEPT
    assert choices["geometry"] == DetailDecision.DEFER
    assert choices["scale"] == DetailDecision.DEFER
    with patch.object(QMessageBox, "warning") as warnings:
        dialog._accept_review()
    warnings.assert_not_called()
    decision = {item.field: item for item in dialog.reviewed().fields}
    assert decision["materials"].origin is DetailOrigin.STORY_CANDIDATE
    assert decision["materials"].source_fingerprint == "story-sha-001"
    assert decision["components"].source_record_id == "STORY-001"
    assert decision["scale"].origin is DetailOrigin.DESIGN_PROPOSAL
    assert decision["scale"].final_value == ""
    reviewed_spec, audit = apply_review(dialog.spec, dialog.reviewed())
    assert "matte graphite-coated metal" in reviewed_spec.canonical_attributes["materials"]
    field_audit = {item["field"]: item for item in json.loads(audit)["fields"]}
    assert field_audit["materials"]["source_fingerprint"] == "story-sha-001"
    assert field_audit["components"]["source_record_id"] == "STORY-001"


def test_qt_operator_change_is_audited_as_edit(qtbot):
    asset = _asset()
    grounded = StoryCAPProposal(_spec(asset), "geometry", ()).ground_against_story(
        asset, _manifest(asset)
    )
    dialog = CAPDetailReviewDialog(
        grounded.specification,
        field_provenance=grounded.field_provenance,
    )
    qtbot.addWidget(dialog)
    for field, value, choice, _ in dialog.rows:
        if field == "materials":
            value.setPlainText("Operator designed entirely new shell")
            choice.setCurrentIndex(choice.findData(DetailDecision.EDIT))
    with patch.object(QMessageBox, "warning") as warnings:
        dialog._accept_review()
    warnings.assert_not_called()
    chosen = next(item for item in dialog.reviewed().fields if item.field == "materials")
    assert chosen.origin is DetailOrigin.OPERATOR_EDITED
    assert chosen.evidence == ""
    assert chosen.final_value == "Operator designed entirely new shell"
