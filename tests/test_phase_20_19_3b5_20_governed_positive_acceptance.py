"""Controlled B.5.20 positive-path acceptance with the real planning contract calculators.

This is an isolated verifier/UI integration fixture, NOT an asset approval
procedure. It never modifies the operator's project or grants Canon authority.
"""

import json
from dataclasses import asdict, replace
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.governed_planning_evidence import (
    ProductionPlanningContracts,
    verified_governed_shot_evidence,
    verified_shots_to_spatial_sources,
)
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.application.story.asset_resolver import AssetBindingStatus, ShotAssetBinding
from vscs.application.story.episode_planning import EpisodePlan, EpisodePlanStatus
from vscs.application.story.scene_planning import ScenePlan, ScenePlanStatus
from vscs.application.story.shot_planning import ShotPlan, ShotPlanStatus
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)

STORY_ID = "STORY-001"
SHOT_ID = "EP-001-SCN-001-SHT-001"
NARRATIVE = (
    "In the empty engineering control room, the diagnostic console "
    "maintains a steady blue glow."
)


def _write(root, name, key, records):
    path = root / "planning" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: records}), encoding="utf-8")


def _governed_fixture(root):
    """Write disposable plans with hashes produced by the actual planners."""
    contracts = ProductionPlanningContracts()
    episode = EpisodePlan(
        episode_id="EP-001",
        story_id=STORY_ID,
        sequence_number=1,
        title="The Quiet Console",
        story_scope="The quiet vessel",
        production_objective="Observe the console",
        target_runtime_seconds=15,
        status=EpisodePlanStatus.READY,
    )
    episode_data = asdict(episode)
    scene = ScenePlan(
        scene_id="EP-001-SCN-001",
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Engineering Control Room",
        story_scope="An empty control room",
        production_objective="Watch the quiet console",
        target_runtime_seconds=15,
        setting_requirement="Engineering control room",
        required_events=("The console remains steady",),
        episode_contract_hash=contracts.episode_contract_hash(episode_data),
        status=ScenePlanStatus.READY,
    )
    scene_data = asdict(scene)
    shot = ShotPlan(
        shot_id=SHOT_ID,
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Uninterrupted Watch",
        narrative_purpose="Observe the diagnostic console",
        production_objective="Maintain a consistent console glow",
        target_runtime_seconds=15,
        required_action=NARRATIVE,
        scene_contract_hash=contracts.scene_contract_hash(scene_data),
        status=ShotPlanStatus.READY,
    )
    shot_data = asdict(shot)
    shot_hash = contracts.shot_contract_hash(shot_data)
    bindings = [
        ShotAssetBinding(
            binding_id=f"{SHOT_ID}-AST-{index:03d}",
            shot_id=SHOT_ID,
            sequence_number=index,
            role=role,
            requirement=name,
            expected_category=category,
            asset_id=asset_id,
            shot_contract_hash=shot_hash,
            status=AssetBindingStatus.READY,
        )
        for index, role, name, category, asset_id in (
            (1, "Location", "Engineering control room", AssetCategory.LOCATION, "CAP-LOC-001"),
            (2, "Prop", "Diagnostic console", AssetCategory.PROP, "CAP-PRP-001"),
        )
    ]
    _write(root, "episode_plans.json", "episodes", [episode_data])
    _write(root, "scene_plans.json", "scenes", [scene_data])
    _write(root, "shot_plans.json", "shots", [shot_data])
    _write(root, "asset_resolutions.json", "bindings", [asdict(item) for item in bindings])
    return episode_data, scene_data, shot_data, bindings


def test_ready_governed_contextual_qt_review_is_advisory(tmp_path, qtbot):
    _governed_fixture(tmp_path)
    verified = verified_governed_shot_evidence(tmp_path, STORY_ID, ProductionPlanningContracts())
    assert len(verified) == 1
    assert verified[0].binding_statuses == ("ready", "ready")
    sources = verified_shots_to_spatial_sources(verified, selected_story_id=STORY_ID)
    assert len(sources) == 1
    spec = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering room",
        canonical_attributes={"architecture": "Unspecified"},
        master_prompt="Draft only",
    )
    assets = (
        Asset.model_construct(asset_id="CAP-LOC-001", name="Engineering control room"),
        Asset.model_construct(asset_id="CAP-PRP-001", name="Diagnostic console"),
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(spec, "architecture", ()),
        story_evidence=(STORY_ID, "Approved", ("CAP-LOC-001", "CAP-PRP-001")),
        narrative_assets=assets,
        shot_sources=sources,
    )
    qtbot.addWidget(dialog)
    dialog.dependencies.setPlainText("CAP-PRP-001|contains|unverified||")
    before = dialog.dependencies.toPlainText()
    with patch.object(QMessageBox, "information") as notice:
        dialog.contextual_shot.click()
    message = notice.call_args.args[2]
    assert "Advisory only" in message
    assert "CAP-PRP-001 in CAP-LOC-001" in message
    assert SHOT_ID in message
    assert dialog.dependencies.toPlainText() == before
    assert dialog._reviewed is None


def test_governed_draft_binding_rejected(tmp_path):
    _, _, _, bindings = _governed_fixture(tmp_path)
    bindings[1] = replace(bindings[1], status=AssetBindingStatus.DRAFT)
    _write(tmp_path, "asset_resolutions.json", "bindings", [asdict(b) for b in bindings])
    with pytest.raises(ShotTextAuthorityError, match="Draft or missing bindings"):
        verified_governed_shot_evidence(tmp_path, STORY_ID, ProductionPlanningContracts())


def test_governed_stale_contract_rejected(tmp_path):
    _, _, shot, _ = _governed_fixture(tmp_path)
    shot["required_action"] = "An unapproved rewrite"
    _write(tmp_path, "shot_plans.json", "shots", [shot])
    with pytest.raises(ShotTextAuthorityError, match="stale or inconsistent"):
        verified_governed_shot_evidence(tmp_path, STORY_ID, ProductionPlanningContracts())
