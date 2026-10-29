"""Approved Story evidence suggestions never edit a CAP without confirmation."""

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def test_evidence_ui_requires_operator_acceptance(qtbot):
    parent = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Draft room",
        canonical_attributes={"architecture": "Undetermined"},
        master_prompt="Draft",
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(parent, "architecture", ()),
        story_evidence=(
            "STORY-001",
            "CAP-PRP-001 is located in CAP-LOC-001.",
            ("CAP-LOC-001", "CAP-PRP-001"),
        ),
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog._review_story_spatial_evidence()
    assert dialog.dependencies.toPlainText() == ""
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._review_story_spatial_evidence()
    assert dialog.dependencies.toPlainText() == "CAP-PRP-001|contains||"
    assert dialog._reviewed is None
