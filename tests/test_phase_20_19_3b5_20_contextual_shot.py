"""B.5.20 contextual suggestions are bounded and never persist CAP dependencies."""

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.contextual_shot_interpretation import (
    suggest_contextual_shot_relationships,
)
from vscs.application.caps.shot_spatial_evidence import ShotSpatialSource
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def _assets():
    return (
        Asset.model_construct(asset_id="CAP-PRP-001", name="Diagnostic Console"),
        Asset.model_construct(asset_id="CAP-LOC-001", name="Engineering Control Room"),
    )


def _source(story="STORY-001", bindings=("CAP-PRP-001", "CAP-LOC-001")):
    return ShotSpatialSource(
        "SHT-001",
        story,
        "Diagnostic Console remains inside Engineering Control Room.",
        bindings,
    )


def test_contextual_registered_bound_assets_only():
    suggestions = suggest_contextual_shot_relationships((_source(),), _assets(), "STORY-001")
    assert len(suggestions) == 1
    assert suggestions[0].child_asset_id == "CAP-PRP-001"
    assert suggestions[0].parent_asset_id == "CAP-LOC-001"
    assert suggestions[0].confidence == "review_required"


def test_contextual_cross_story_and_missing_binding_rejected():
    assert not suggest_contextual_shot_relationships(
        (_source(story="STORY-OTHER"),), _assets(), "STORY-001"
    )
    assert not suggest_contextual_shot_relationships(
        (_source(bindings=("CAP-PRP-001",)),), _assets(), "STORY-001"
    )


def test_contextual_duplicate_name_is_ambiguous():
    conflicting = (
        *_assets(),
        Asset.model_construct(asset_id="CAP-PRP-002", name="Diagnostic Console"),
    )
    source = _source(bindings=("CAP-PRP-001", "CAP-PRP-002", "CAP-LOC-001"))
    assert not suggest_contextual_shot_relationships((source,), conflicting, "STORY-001")


def test_contextual_review_is_non_mutating(qtbot):
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering",
        canonical_attributes={"architecture": "Unknown"},
        master_prompt="Draft",
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(spec, "architecture", ()),
        story_evidence=("STORY-001", "Approved", ("CAP-LOC-001", "CAP-PRP-001")),
        narrative_assets=_assets(),
        shot_sources=(_source(),),
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "information") as shown:
        dialog.contextual_shot.click()
    assert "CAP-PRP-001 in CAP-LOC-001" in shown.call_args.args[2]
    assert dialog.dependencies.toPlainText() == ""


def test_audit_location_first_wording_is_advisory():
    source = ShotSpatialSource(
        "SHT-001",
        "STORY-001",
        "In the empty engineering control room, the diagnostic console maintains a steady blue glow.",
        ("CAP-LOC-001", "CAP-PRP-001"),
    )
    suggestions = suggest_contextual_shot_relationships((source,), _assets(), "STORY-001")
    assert len(suggestions) == 1
    assert suggestions[0].child_asset_id == "CAP-PRP-001"
    assert suggestions[0].parent_asset_id == "CAP-LOC-001"
    assert suggestions[0].confidence == "review_required"
