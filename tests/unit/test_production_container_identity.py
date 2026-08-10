"""Tests for Phase 16.2a.8.3a production containers and scene identity."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel

from vscs.application.ssie import Scene
from vscs.application.story import (
    ProductionContainerType,
    build_scene_id,
    infer_container_type,
    normalize_container_id,
)
from vscs.presentation.dialogs.production_container_scene_editor_dialog import (
    ProductionContainerSceneEditorDialog,
)


def _scene(container_id: str = "EP-001") -> Scene:
    return Scene(
        scene_id=f"{container_id}-SCN-001",
        episode_id=container_id,
        sequence_number=1,
        heading="EXT. XORIX ORBIT - DAY",
        location_asset_id="LOC-XORIX-ORBIT",
        summary="The production opens above Xorix.",
        scene_name="Opening View",
    )


def test_container_identity_helpers_support_all_production_types() -> None:
    assert infer_container_type("EP-001") is ProductionContainerType.EPISODE
    assert infer_container_type("T01") is ProductionContainerType.TRAILER
    assert infer_container_type("TEASER-01") is ProductionContainerType.TEASER
    assert infer_container_type("PROMO-01") is ProductionContainerType.PROMO
    assert infer_container_type("TEST-01") is ProductionContainerType.TEST
    assert infer_container_type("SPECIAL-01") is ProductionContainerType.SPECIAL
    assert normalize_container_id("trailer book 1", ProductionContainerType.TRAILER) == (
        "TRAILER-BOOK-1"
    )
    assert build_scene_id("T01", 3) == "T01-SCN-003"


def test_new_scene_defaults_to_episode_container(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionContainerSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.container_type is ProductionContainerType.EPISODE
    assert dialog.container_id == "EP-001"
    assert dialog.scene_id_edit.text() == "EP-001-SCN-001"
    label = dialog._find_form_layout().labelForField(dialog.episode_id_edit)
    assert isinstance(label, QLabel)
    assert label.text() == "Container ID *"


def test_trailer_selection_generates_trailer_scene_identity(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionContainerSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    index = dialog.production_type_combo.findData(ProductionContainerType.TRAILER)
    if index < 0:
        index = dialog.production_type_combo.findData(ProductionContainerType.TRAILER.value)
    assert index >= 0
    dialog.production_type_combo.setCurrentIndex(index)

    assert dialog.container_type is ProductionContainerType.TRAILER
    assert dialog.episode_id_edit.text() == "T01"
    assert dialog.scene_id_edit.text() == "T01-SCN-001"
    assert "Trailer" in dialog.summary_label.text()


def test_custom_container_id_is_normalized_and_updates_scene_id(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionContainerSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    dialog.episode_id_edit.setText("trailer book one")
    dialog._normalize_container_field()

    assert dialog.episode_id_edit.text() == "TRAILER-BOOK-ONE"
    assert dialog.scene_id_edit.text() == "TRAILER-BOOK-ONE-SCN-001"


def test_existing_scene_infers_type_and_locks_identity_controls(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionContainerSceneEditorDialog(_scene("T01"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.container_type is ProductionContainerType.TRAILER
    assert not dialog.production_type_combo.isEnabled()
    assert dialog.episode_id_edit.isReadOnly()
    assert not dialog.sequence_spin.isEnabled()
    assert dialog.scene_id_edit.text() == "T01-SCN-001"


def test_container_controls_have_vkf_and_live_documentation(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ProductionContainerSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert (
        dialog.knowledge_provider.topic_for(dialog.production_type_combo) == "scene.production_type"
    )
    assert dialog.knowledge_provider.topic_for(dialog.episode_id_edit) == "scene.container_id"
    dialog.show_live_topic("scene.production_type")
    assert dialog.documentation_panel.topic_id == "scene.production_type"
    assert "Production Type" in dialog.documentation_panel.content_label.text()
