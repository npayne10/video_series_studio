"""Disposable project acceptance: persisted Shot text reaches Qt Draft review only via scope."""

from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.authoritative_shot_text import (
    assert_shot_text_fresh,
    capture_authoritative_shot_text,
)
from vscs.application.caps.story_scene_authority import StorySceneAuthority
from vscs.application.caps.story_specification import StoryCAPProposal
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.application.shots.models import ProductionShot
from vscs.application.shots.service import ShotPlanningService
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs.story_cap_specification_dialog import (
    StoryCAPSpecificationDialog,
)


class _Scenes:
    def list_scenes(self):
        return (SimpleNamespace(scene_id="SCN-001"),)


def test_disposable_persisted_shot_evidence_reaches_review_after_assignment(qtbot, tmp_path):
    projects = SimpleNamespace(project_directory=tmp_path)
    reader = ShotPlanningService(projects)
    reader.save_shot(
        ProductionShot(
            shot_id="SCN-001-SHT-001",
            scene_id="SCN-001",
            sequence_number=1,
            title="Control room",
            description="Diagnostic Console inside Engineering Control Room.",
            subject_asset_ids=("CAP-PRP-001",),
            required_asset_ids=("CAP-LOC-001",),
        )
    )
    ledger = StorySceneAuthority(tmp_path, _Scenes())
    scope = ledger.assign("STORY-001", "approved-fingerprint", ("SCN-001",))
    snapshot = capture_authoritative_shot_text(reader, scope, "approved-fingerprint")
    evidence = assert_shot_text_fresh(
        snapshot, reader, scope, "approved-fingerprint"
    )
    specification = CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Control room",
        canonical_attributes={"architecture": "Unknown"},
        master_prompt="Draft only",
    )
    dialog = StoryCAPSpecificationDialog(
        StoryCAPProposal(specification, "architecture", ()),
        story_evidence=("STORY-001", "Approved", ("CAP-LOC-001", "CAP-PRP-001")),
        narrative_assets=(
            Asset.model_construct(asset_id="CAP-PRP-001", name="Diagnostic Console"),
            Asset.model_construct(asset_id="CAP-LOC-001", name="Engineering Control Room"),
        ),
        shot_sources=evidence,
    )
    qtbot.addWidget(dialog)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
        dialog.shot_spatial.click()
    assert dialog.dependencies.toPlainText() == ""
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
        dialog.shot_spatial.click()
    assert "CAP-PRP-001|contains||" in dialog.dependencies.toPlainText()
    assert not (tmp_path / "caps").exists()
