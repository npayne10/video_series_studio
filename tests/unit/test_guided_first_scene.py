"""Tests for Phase 16.2a.8.5.4.4 guided first-scene workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)
from vscs.presentation.onboarding import OnboardingOutcome


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "guided-first-scene.ini"), QSettings.Format.IniFormat)


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


def _start(
    dialog: GuidedFirstSceneEditorDialog,
    qapp: QApplication,
) -> None:
    dialog.show()
    qapp.processEvents()
    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()


def test_required_scene_identity_step_waits_for_editing_to_finish(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        location_assets=(_location(),),
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start(dialog, qapp)
    dialog.onboarding.go_to(3)
    qapp.processEvents()

    assert not dialog.tour_overlay.next_button.isEnabled()
    assert dialog.tour_overlay.try_button.isVisible()

    dialog.tour_overlay.try_button.click()
    qapp.processEvents()

    assert not dialog.tour_overlay.isVisible()
    assert dialog.scene_name_edit.hasFocus()

    QTest.keyClicks(dialog.scene_name_edit, "Arrival at Xorix")
    assert not dialog.tour_overlay.isVisible()

    QTest.keyClick(dialog.scene_name_edit, Qt.Key.Key_Tab)
    qapp.processEvents()
    assert dialog.heading_edit.hasFocus()
    assert not dialog.tour_overlay.isVisible()

    QTest.keyClicks(dialog.heading_edit, "EXT. XORIX ORBIT - DAY")
    qapp.processEvents()
    assert dialog.heading_edit.text() == "EXT. XORIX ORBIT - DAY"
    assert not dialog.tour_overlay.isVisible()

    QTest.keyClick(dialog.heading_edit, Qt.Key.Key_Tab)
    qapp.processEvents()

    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.next_button.isEnabled()
    assert "Completed" in dialog.tour_overlay.action_hint_label.text()


def test_location_step_routes_try_it_and_returns_when_selected(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        location_assets=(_location(),),
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start(dialog, qapp)
    dialog.onboarding.go_to(4)
    qapp.processEvents()

    assert not dialog.tour_overlay.next_button.isEnabled()
    dialog.tour_overlay.try_button.click()
    qapp.processEvents()
    assert dialog.location_combo.hasFocus()

    dialog.location_combo.setCurrentIndex(1)
    qapp.processEvents()

    assert dialog.selected_location_id() == "LOC-XORIX-ORBIT"
    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.next_button.isEnabled()


def test_optional_steps_remain_available_without_forcing_content(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start(dialog, qapp)

    for index in (5, 6, 7):
        dialog.onboarding.go_to(index)
        qapp.processEvents()
        assert dialog.tour_overlay.next_button.isEnabled()
        assert not dialog.tour_overlay.try_button.isVisible()
        assert "optional" in dialog.tour_overlay.action_hint_label.text().lower()


def test_validation_try_it_focuses_first_missing_field(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        location_assets=(_location(),),
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start(dialog, qapp)
    dialog.onboarding.go_to(9)
    qapp.processEvents()

    assert not dialog.tour_overlay.next_button.isEnabled()
    dialog.tour_overlay.try_button.click()
    qapp.processEvents()

    assert dialog.scene_name_edit.hasFocus()
    assert dialog.documentation_panel.topic_id == "scene.name"


def test_valid_final_step_creates_scene_and_completes_onboarding(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        location_assets=(_location(),),
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start(dialog, qapp)
    dialog.scene_name_edit.setText("Arrival at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    dialog.location_combo.setCurrentIndex(1)
    dialog.summary_edit.setPlainText("The crew sees Xorix for the first time.")
    dialog._validate()
    dialog.onboarding.go_to(dialog.onboarding.sequence.total_steps - 1)
    qapp.processEvents()

    assert dialog.save_button.isEnabled()
    assert dialog.tour_overlay.next_button.text() == "Create Scene"
    assert dialog.tour_overlay.next_button.isEnabled()

    dialog.tour_overlay.next_button.click()
    qapp.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.onboarding.state.outcome is OnboardingOutcome.COMPLETED
