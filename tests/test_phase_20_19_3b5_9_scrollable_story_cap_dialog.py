"""Story CAP review must remain usable on smaller screens."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialogButtonBox, QScrollArea

from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def test_story_cap_review_scrolls_with_fixed_action_buttons(qtbot):
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"architecture": "Interior vessel compartment"},
        master_prompt="Unapproved reference draft",
    )
    proposal = StoryCAPProposal(
        specification=spec, suggested_attribute_key="architecture", limitations=("Unapproved",)
    )
    dialog = StoryCAPSpecificationDialog(proposal)
    qtbot.addWidget(dialog)
    dialog.resize(540, 390)
    dialog.show()
    area = dialog.findChild(QScrollArea)
    actions = dialog.findChild(QDialogButtonBox)
    assert area is not None
    assert actions is not None
    assert area.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert area.verticalScrollBar().maximum() > 0
    assert actions.isVisible()
    assert dialog.dependencies is not None
