"""Tests for Phase 16.2a.8.4 validation explanations."""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QApplication

from vscs.application.ssie import Scene
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.validation_explanations_scene_editor_dialog import (
    ValidationExplanationsSceneEditorDialog,
    ValidationSeverity,
)


def _location() -> Asset:
    now = datetime.now(UTC)
    return Asset(
        id=1,
        asset_id="LOC-XORIX-ORBIT",
        name="Xorix Orbit",
        category=AssetCategory.LOCATION,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
        created_at=now,
        updated_at=now,
    )


def _complete(dialog: ValidationExplanationsSceneEditorDialog) -> None:
    dialog.scene_name_edit.setText("Arrival at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    location_index = dialog.location_combo.findData("LOC-XORIX-ORBIT")
    assert location_index >= 0
    dialog.location_combo.setCurrentIndex(location_index)
    dialog.summary_edit.setPlainText("The crew enters orbit and sees Xorix for the first time.")


def test_missing_fields_explain_requirement_and_reason(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ValidationExplanationsSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    text = dialog.validation_label.text()

    assert not dialog.save_button.isEnabled()
    assert "must be resolved before saving" in text
    assert "Scene name" in text
    assert "Story Browser" in text
    assert "Primary location" in text
    assert "continuity" in text
    assert "Scene summary" in text
    assert "SSIE" in text


def test_complete_scene_reports_ready_to_save(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ValidationExplanationsSceneEditorDialog(location_assets=(_location(),))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    _complete(dialog)

    assert dialog.save_button.isEnabled()
    assert dialog.validation_explanations == ()
    assert "Ready to save" in dialog.validation_label.text()


def test_malformed_container_id_blocks_save_with_identity_explanation(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ValidationExplanationsSceneEditorDialog(location_assets=(_location(),))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _complete(dialog)

    dialog.episode_id_edit.setText("Trailer / Book 1")

    assert not dialog.save_button.isEnabled()
    issue = next(
        item for item in dialog.validation_explanations if item.topic_id == "scene.container_id"
    )
    assert issue.severity is ValidationSeverity.ERROR
    assert "letters, numbers and single hyphens" in issue.message
    assert "ACPP" in issue.reason


def test_unavailable_references_are_non_blocking_warnings(
    qtbot: object,
    qapp: QApplication,
) -> None:
    scene = Scene(
        scene_id="T01-SCN-001",
        episode_id="T01",
        sequence_number=1,
        heading="EXT. XORIX ORBIT - DAY",
        location_asset_id="LOC-MISSING",
        summary="The trailer opens above Xorix.",
        participant_asset_ids=("CHR-MISSING",),
        required_asset_ids=("SHP-MISSING",),
        scene_name="Trailer Opening",
    )
    dialog = ValidationExplanationsSceneEditorDialog(scene)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    warnings = tuple(
        issue
        for issue in dialog.validation_explanations
        if issue.severity is ValidationSeverity.WARNING
    )

    assert dialog.save_button.isEnabled()
    assert len(warnings) == 3
    assert "review these production warnings" in dialog.validation_label.text()
    assert all("preserved" in issue.reason for issue in warnings)


def test_save_shortcut_focuses_first_issue_and_updates_live_help(
    qtbot: object,
    qapp: QApplication,
) -> None:
    dialog = ValidationExplanationsSceneEditorDialog()
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()

    dialog._save_from_shortcut()
    qapp.processEvents()

    assert dialog.focusWidget() is dialog.scene_name_edit
    assert dialog.documentation_panel.topic_id == "scene.name"
