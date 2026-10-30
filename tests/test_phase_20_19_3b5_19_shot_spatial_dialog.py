"""Shot evidence UI cannot silently invent a relationship when reader is unavailable."""

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def test_missing_verified_shot_source_leaves_review_unchanged(qtbot):
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Control room",
        canonical_attributes={"architecture": "Unknown"},
        master_prompt="Draft proposal only",
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(spec, "architecture", ()),
        story_evidence=("STORY-001", "Approved description", ("CAP-LOC-001",)),
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "information") as info:
        dialog._review_shot_spatial()
    info.assert_called_once()
    assert "No verified Shot text reader connected" in info.call_args.args[2]
    assert not dialog.dependencies.toPlainText()
