"""Tests for Phase 16.2a scene identity and location selection UX."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QApplication

from vscs.application.ssie import Scene
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.scene_editor_dialog import SceneEditorDialog


def _asset(
    asset_id: str,
    name: str,
    category: AssetCategory = AssetCategory.LOCATION,
) -> Asset:
    now = datetime.now(UTC)
    return Asset(
        id=1,
        asset_id=asset_id,
        name=name,
        category=category,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
        created_at=now,
        updated_at=now,
    )


def _locations() -> tuple[Asset, ...]:
    return (
        _asset("LOC-XORIX-ORBIT", "Xorix Orbit"),
        _asset("ENV-XORIX-FOREST", "Xorix Forest", AssetCategory.ENVIRONMENT),
    )


def test_new_scene_generates_read_only_identity(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog(
        default_episode_id="EP-004",
        suggested_sequence=7,
        scene_id_factory=lambda episode, sequence: f"{episode}-SCN-{sequence:03d}",
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.scene_id_edit.text() == "EP-004-SCN-007"
    assert dialog.scene_id_edit.isReadOnly()

    dialog.sequence_spin.setValue(8)

    assert dialog.scene_id_edit.text() == "EP-004-SCN-008"


def test_save_remains_disabled_until_required_fields_are_complete(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog(location_assets=_locations())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert not dialog.save_button.isEnabled()
    assert "scene name" in dialog.validation_label.text()

    dialog.scene_name_edit.setText("Emergence at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    dialog.location_combo.setCurrentIndex(1)
    dialog.summary_edit.setPlainText("The Iron Horizon arrives above Xorix.")

    assert dialog.save_button.isEnabled()
    assert dialog.validation_label.text() == ""


def test_dialog_returns_selected_canonical_location_id(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog(
        default_episode_id="EP-002",
        suggested_sequence=3,
        location_assets=_locations(),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.scene_name_edit.setText("First Sight of Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    location_index = dialog.location_combo.findData("LOC-XORIX-ORBIT")
    assert location_index >= 0
    dialog.location_combo.setCurrentIndex(location_index)
    dialog.summary_edit.setPlainText("The crew sees Xorix for the first time.")

    scene = dialog.scene()

    assert scene.scene_name == "First Sight of Xorix"
    assert scene.heading == "EXT. XORIX ORBIT - DAY"
    assert scene.scene_id == "EP-002-SCN-003"
    assert scene.location_asset_id == "LOC-XORIX-ORBIT"


def test_location_selector_supports_search_by_exact_asset_name(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog(location_assets=_locations())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.location_combo.setEditText("Xorix Forest")

    assert dialog.selected_location_id() == "ENV-XORIX-FOREST"


def test_empty_location_catalog_explains_how_to_add_assets(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = SceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.location_combo.count() == 1
    assert "Asset Manager" in dialog.location_help.text()
    assert not dialog.save_button.isEnabled()


def test_editing_preserves_existing_unavailable_location_reference(
    qtbot: object,
    qapp: QApplication,
) -> None:
    scene = Scene(
        scene_id="EP-001-SCN-004",
        episode_id="EP-001",
        sequence_number=4,
        heading="INT. BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The bridge crew receives an alert.",
        scene_name="The Alert",
    )
    dialog = SceneEditorDialog(scene, location_assets=_locations())
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.sequence_spin.setValue(9)
    dialog.episode_id_edit.setText("EP-003")

    assert dialog.scene_id_edit.text() == "EP-001-SCN-004"
    assert dialog.scene_name_edit.text() == "The Alert"
    assert dialog.selected_location_id() == "LOC-BRIDGE"
    assert "not currently present" in dialog.location_help.text()
