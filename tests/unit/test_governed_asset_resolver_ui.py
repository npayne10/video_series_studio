"""UI coverage for the Phase 19.3.4 governed Asset Resolver."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from PySide6.QtWidgets import QMessageBox

from vscs.application.asset_resolution import AssetResolutionStatus
from vscs.application.story import (
    AssetBindingStatus,
    ShotAssetInferenceSource,
    ShotAssetRequirementProposal,
    ShotPlan,
)
from vscs.domain.assets import AssetCategory
from vscs.presentation.widgets.governed_asset_resolver import (
    AssetBindingEditorDialog,
    GovernedAssetResolverDialog,
)


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Reveal Xorix",
        narrative_purpose="Reveal Xorix.",
        production_objective="Orient the audience.",
        target_runtime_seconds=10,
        required_action="The ship crosses frame.",
        scene_contract_hash="scene-contract",
    )


def test_asset_editor_excludes_camera_lighting_and_reference_categories(qtbot) -> None:
    service = cast(
        Any,
        SimpleNamespace(
            available_assets=lambda _category: (),
        ),
    )
    dialog = AssetBindingEditorDialog(service, _shot())
    qtbot.addWidget(dialog)

    categories = {
        dialog.category_combo.itemData(index) for index in range(dialog.category_combo.count())
    }

    assert AssetCategory.CHARACTER in categories
    assert AssetCategory.SHIP in categories
    assert AssetCategory.CAMERA not in categories
    assert AssetCategory.LIGHTING not in categories
    assert AssetCategory.REFERENCE not in categories
    assert str(dialog.asset_combo.currentData() or "") == ""
    assert "Unbound" in dialog.readiness_label.text()


def test_asset_resolver_exposes_automated_requirement_analysis_and_human_apply(
    qtbot,
    monkeypatch,
) -> None:
    shot = _shot()
    proposal = ShotAssetRequirementProposal(
        proposal_id=f"{shot.shot_id}-AIR-001",
        shot_id=shot.shot_id,
        role="Required Ship",
        requirement="Iron Horizon is required by the governed Shot.",
        expected_category=AssetCategory.SHIP,
        matched_asset_id="CAP-SHP-IRON-HORIZON",
        matched_asset_name="Iron Horizon",
        confidence=1.0,
        source=ShotAssetInferenceSource.CANONICAL_MATCH,
        rationale="Explicit canonical asset name occurs in governed Shot text.",
        canonical_status="resolved",
    )
    applied: list[tuple[ShotAssetRequirementProposal, ...]] = []

    service = cast(
        Any,
        SimpleNamespace(
            shots=SimpleNamespace(
                plan=lambda _shot_id: shot,
                is_production_ready=lambda _shot: True,
            ),
            semantic_provider=None,
            list_bindings=lambda **_kwargs: (),
            infer_requirements=lambda _shot_id: (proposal,),
            apply_inferred_requirements=lambda _shot_id, proposals: (
                applied.append(proposals) or (SimpleNamespace(),)
            ),
        ),
    )
    monkeypatch.setattr(
        "vscs.presentation.widgets.governed_asset_resolver.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        "vscs.presentation.widgets.governed_asset_resolver.QMessageBox.information",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok,
    )

    dialog = GovernedAssetResolverDialog(service, shot)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog.analyze_button.objectName() == "analyzeShotAssetRequirements"
    assert dialog.analyze_button.isEnabled()
    assert "1 canonical match" in dialog.inference_label.text()
    assert "AI semantic inference not configured" in dialog.inference_label.text()

    dialog.analyze_button.click()

    assert applied == [(proposal,)]


def test_partial_draft_binding_is_not_mislabelled_as_changed(qtbot) -> None:
    shot = _shot()
    binding = SimpleNamespace(
        binding_id=f"{shot.shot_id}-AST-001",
        role="Location",
        expected_category=AssetCategory.LOCATION,
        requirement="Bridge is required.",
        asset_id="CAP-LOC-008",
        notes="",
        status=AssetBindingStatus.DRAFT,
    )
    service = cast(
        Any,
        SimpleNamespace(
            shots=SimpleNamespace(
                plan=lambda _shot_id: shot,
                is_production_ready=lambda _shot: True,
            ),
            semantic_provider=None,
            list_bindings=lambda **_kwargs: (binding,),
            infer_requirements=lambda _shot_id: (),
            resolution=lambda _binding: SimpleNamespace(status=AssetResolutionStatus.PARTIAL),
            is_asset_current=lambda _binding: False,
            is_upstream_current=lambda _binding: True,
            is_production_ready=lambda _binding: False,
        ),
    )

    dialog = GovernedAssetResolverDialog(service, shot)
    qtbot.addWidget(dialog)

    assert dialog.table.item(0, 5).text() == "Partial"
    assert dialog.table.item(0, 6).text() == "Draft"

