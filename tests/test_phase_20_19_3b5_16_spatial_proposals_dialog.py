"""Offline proposal action never applies a relationship without operator consent."""

from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def _spec(asset_id, category, constraints=()):
    return CAPStructuredSpecification(
        asset_id=asset_id,
        category=category,
        design_intent="Unapproved test design",
        canonical_attributes={
            "architecture" if category is AssetCategory.LOCATION else "geometry": "Unknown"
        },
        master_prompt="Test only",
        dependency_asset_ids=tuple(item.target_asset_id for item in constraints),
        dependency_constraints=constraints,
    )


def test_offline_suggestion_requires_confirmation_and_does_not_write(qtbot):
    parent = _spec("CAP-LOC-001", AssetCategory.LOCATION)
    child = _spec(
        "CAP-PRP-001",
        AssetCategory.PROP,
        (DependencyConstraint(target_asset_id=parent.asset_id, relation=DependencyRelation.LOCATED_IN),),
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(parent, "architecture", ()), spatial_candidates=(child,)
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog._analyze_spatial_relationships()
    assert dialog.dependencies.toPlainText() == ""
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog._analyze_spatial_relationships()
    assert dialog.dependencies.toPlainText() == "CAP-PRP-001|contains||"
    assert dialog._reviewed is None
