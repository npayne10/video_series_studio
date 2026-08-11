"""UI coverage for the Phase 19.3.4 governed Asset Resolver."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from vscs.application.story import ShotPlan
from vscs.domain.assets import AssetCategory
from vscs.presentation.widgets.governed_asset_resolver import AssetBindingEditorDialog


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
