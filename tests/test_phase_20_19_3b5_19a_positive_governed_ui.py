"""Ready governed Shot evidence reaches operator review without Canon persistence."""

import json
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

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


def _project(root):
    """Write an isolated governed planning fixture using real contract functions."""
    calculator = ProductionPlanningContracts()
    episode = {
        "episode_id": "EP-001",
        "story_id": "STORY-001",
        "sequence_number": 1,
        "title": "Episode",
        "story_scope": "Observation",
        "production_objective": "Show a quiet vessel",
        "target_runtime_seconds": 45,
        "status": "ready",
    }
    scene = {
        "scene_id": "EP-001-SCN-001",
        "episode_id": "EP-001",
        "sequence_number": 1,
        "title": "Engineering",
        "story_scope": "Observation",
        "production_objective": "Show engineering room",
        "target_runtime_seconds": 45,
        "setting_requirement": "Engineering Control Room",
        "required_events": ["Diagnostic pulse"],
        "status": "ready",
        "episode_contract_hash": calculator.episode_contract_hash(episode),
    }
    shot = {
        "shot_id": "EP-001-SCN-001-SHT-001",
        "scene_id": "EP-001-SCN-001",
        "sequence_number": 1,
        "title": "Console",
        "narrative_purpose": "Watch the console",
        "production_objective": "Show control room",
        "target_runtime_seconds": 15,
        "required_action": "Diagnostic Console inside Engineering Control Room.",
        "status": "ready",
        "scene_contract_hash": calculator.scene_contract_hash(scene),
    }
    binding = {
        "shot_id": "EP-001-SCN-001-SHT-001",
        "asset_id": "CAP-PRP-001",
        "status": "ready",
        "shot_contract_hash": calculator.shot_contract_hash(shot),
    }
    folder = root / "planning"
    folder.mkdir()
    for name, key, records in (
        ("episode_plans.json", "episodes", [episode]),
        ("scene_plans.json", "scenes", [scene]),
        ("shot_plans.json", "shots", [shot]),
        ("asset_resolutions.json", "bindings", [binding]),
    ):
        (folder / name).write_text(json.dumps({key: records}), encoding="utf-8")


def test_ready_governed_evidence_requires_operator_confirmation(qtbot, tmp_path):
    _project(tmp_path)
    file = tmp_path / "planning" / "asset_resolutions.json"
    payload = json.loads(file.read_text(encoding="utf-8"))
    location_binding = dict(payload["bindings"][0])
    location_binding["asset_id"] = "CAP-LOC-001"
    payload["bindings"].append(location_binding)
    file.write_text(json.dumps(payload), encoding="utf-8")
    evidence = verified_governed_shot_evidence(tmp_path, "STORY-001", ProductionPlanningContracts())
    sources = verified_shots_to_spatial_sources(evidence, selected_story_id="STORY-001")
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


def test_governed_source_message_does_not_claim_legacy_shot_authority(qtbot):
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Control room",
        canonical_attributes={"architecture": "Unknown"},
        master_prompt="Draft only",
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(spec, "architecture", ()),
        story_evidence=("STORY-001", "Approved", ("CAP-LOC-001",)),
        shot_evidence_status=(
            "Governed Shot source: planning/shot_plans.json. "
            "Draft or missing bindings are not approved evidence."
        ),
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "information") as info:
        dialog.shot_spatial.click()
    message = info.call_args.args[2]
    assert "planning/shot_plans.json" in message
    assert "Draft or missing bindings" in message
    assert "story/shots.json" not in message
