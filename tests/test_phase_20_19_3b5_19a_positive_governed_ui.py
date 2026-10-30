"""Ready governed Shot evidence reaches operator review without Canon persistence."""

import json
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from test_phase_20_19_3b5_19a_real_planner_contracts import _project
from vscs.application.caps.governed_planning_evidence import (
    ProductionPlanningContracts,
    verified_governed_shot_evidence,
    verified_shots_to_spatial_sources,
)
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


def test_ready_governed_evidence_requires_operator_confirmation(qtbot, tmp_path):
    _project(tmp_path)
    file = tmp_path / "planning" / "asset_resolutions.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    location_binding = dict(payload["bindings"][0])
    location_binding["asset_id"] = "CAP-LOC-001"
    payload["bindings"].append(location_binding)
    file.write_text(json.dumps(payload), encoding="utf-8")
    evidence = verified_governed_shot_evidence(
        tmp_path, "STORY-001", ProductionPlanningContracts()
    )
    sources = verified_shots_to_spatial_sources(
        evidence, selected_story_id="STORY-001"
    )
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Control room",
        canonical_attributes={"architecture": "Unknown"},
        master_prompt="Draft only",
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(spec, "architecture", ()),
        story_evidence=("STORY-001", "Approved", ("CAP-LOC-001", "CAP-PRP-001")),
        narrative_assets=(
            Asset.model_construct(asset_id="CAP-PRP-001", name="Diagnostic Console"),
            Asset.model_construct(asset_id="CAP-LOC-001", name="Engineering Control Room"),
        ),
        shot_sources=sources,
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog.shot_spatial.click()
    assert dialog.dependencies.toPlainText() == ""
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog.shot_spatial.click()
    assert "CAP-PRP-001|contains||" in dialog.dependencies.toPlainText()
    assert not (tmp_path / "caps").exists()
    assert not (tmp_path / "story").exists()
