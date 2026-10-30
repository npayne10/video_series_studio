"""Narrative relationship suggestions remain explicitly review-gated."""

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def test_narrative_proposal_can_be_declined_or_accepted(qtbot):
    parent = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Room",
        canonical_attributes={"architecture": "Undetermined"},
        master_prompt="Draft only",
    )
    assets = (
        Asset.model_construct(asset_id="CAP-PRP-001", name="Diagnostic Console"),
        Asset.model_construct(asset_id="CAP-LOC-001", name="Engineering Control Room"),
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(parent, "architecture", ()),
        story_evidence=(
            "STORY-001",
            "Diagnostic Console is located in Engineering Control Room.",
            ("CAP-PRP-001", "CAP-LOC-001"),
        ),
        narrative_assets=assets,
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog._review_narrative_spatial()
    assert not dialog.dependencies.toPlainText()
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._review_narrative_spatial()
    assert dialog.dependencies.toPlainText() == "CAP-PRP-001|contains||"
    assert dialog._reviewed is None
