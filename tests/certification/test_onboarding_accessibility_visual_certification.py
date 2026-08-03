"""Phase 16.2a.8.5.4.5.2.4 accessibility and visual certification."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from tests.certification.accessibility_visual_matrix import (
    ACCESSIBILITY_VISUAL_MATRIX,
    accessibility_visual_areas,
    accessibility_visual_test_nodes,
)
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)


EXPECTED_AREAS = (
    "Accessible onboarding identity",
    "Descriptive controls",
    "Stable object names",
    "Consistent action language",
    "Visible keyboard focus",
    "Palette resilience",
    "Beginner and expert consistency",
    "Readable validation state",
)


def _settings(tmp_path: Path, name: str) -> QSettings:
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


def _show(dialog: GuidedFirstSceneEditorDialog, qapp: QApplication) -> None:
    dialog.show()
    qapp.processEvents()


def _start_guide(
    dialog: GuidedFirstSceneEditorDialog,
    qapp: QApplication,
) -> None:
    _show(dialog, qapp)
    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.tour_overlay.isVisible()


def test_accessibility_visual_matrix_covers_every_approved_area() -> None:
    assert accessibility_visual_areas() == EXPECTED_AREAS
    assert len(ACCESSIBILITY_VISUAL_MATRIX) == len(EXPECTED_AREAS)
    nodes = accessibility_visual_test_nodes()
    assert len(nodes) == len(set(nodes))


def test_accessibility_visual_matrix_references_existing_test_files() -> None:
    root = Path(__file__).resolve().parents[2]
    missing = {
        node.split("::", maxsplit=1)[0]
        for node in accessibility_visual_test_nodes()
        if not (root / node.split("::", maxsplit=1)[0]).is_file()
    }
    assert not missing


def test_onboarding_surfaces_have_accessible_names(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "accessible-names.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    assert dialog.welcome_overlay.accessibleName() == "Welcome to the VSCS Scene Editor"
    assert dialog.beginner_mode_checkbox.accessibleName() == "Enable Beginner Mode"
    assert dialog.restart_tour_button.accessibleName() == "Start Scene Editor Tour"

    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.tour_overlay.accessibleName() == "Guided interface tour"


def test_primary_controls_have_names_and_tooltips(
    qtbot: object,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "descriptions.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    controls = (
        dialog.beginner_mode_checkbox,
        dialog.restart_tour_button,
        dialog.welcome_overlay.start_button,
        dialog.welcome_overlay.skip_button,
    )
    for control in controls:
        assert control.objectName()
        assert control.toolTip().strip()

    assert dialog.scene_name_edit.toolTip().strip()
    assert dialog.heading_edit.toolTip().strip()
    assert dialog.location_combo.toolTip().strip()


def test_certified_object_names_are_unique_and_stable(
    qtbot: object,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "object-names.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    names = (
        dialog.beginner_mode_checkbox.objectName(),
        dialog.restart_tour_button.objectName(),
        dialog.welcome_overlay.objectName(),
        dialog.welcome_overlay.start_button.objectName(),
        dialog.welcome_overlay.skip_button.objectName(),
        dialog.tour_overlay.objectName(),
        dialog.tour_overlay.card.objectName(),
        dialog.tour_overlay.next_button.objectName(),
        dialog.tour_overlay.previous_button.objectName(),
        dialog.tour_overlay.try_button.objectName(),
        dialog.tour_overlay.skip_button.objectName(),
    )
    assert all(names)
    assert len(names) == len(set(names))


def test_onboarding_action_language_is_consistent(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "language.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    assert dialog.welcome_overlay.start_button.text() == "Start Guide"
    assert dialog.welcome_overlay.skip_button.text() == "Skip"
    assert dialog.restart_tour_button.text() == "Start Scene Editor Tour…"

    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.tour_overlay.previous_button.text() == "Previous"
    assert dialog.tour_overlay.next_button.text() == "Next"
    assert dialog.tour_overlay.try_button.text() == "Try It"
    assert dialog.tour_overlay.skip_button.text() == "Skip Tour"

    dialog.onboarding.go_to(dialog.onboarding.sequence.total_steps - 1)
    qapp.processEvents()
    assert dialog.tour_overlay.next_button.text() == "Create Scene"


def test_visible_overlays_assign_focus_to_an_action(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "focus.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)

    assert dialog.welcome_overlay.start_button.hasFocus()
    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.tour_overlay.next_button.hasFocus()

    dialog.onboarding.go_to(3)
    qapp.processEvents()
    assert dialog.tour_overlay.try_button.isVisible()
    assert dialog.tour_overlay.try_button.hasFocus()


def test_onboarding_renders_with_light_and_dark_palettes(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    original = QPalette(qapp.palette())
    palettes = []

    light = QPalette(original)
    light.setColor(QPalette.ColorRole.Window, QColor("#f4f4f4"))
    light.setColor(QPalette.ColorRole.WindowText, QColor("#111111"))
    light.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    light.setColor(QPalette.ColorRole.Text, QColor("#111111"))
    palettes.append(light)

    dark = QPalette(original)
    dark.setColor(QPalette.ColorRole.Window, QColor("#252525"))
    dark.setColor(QPalette.ColorRole.WindowText, QColor("#f2f2f2"))
    dark.setColor(QPalette.ColorRole.Base, QColor("#303030"))
    dark.setColor(QPalette.ColorRole.Text, QColor("#f2f2f2"))
    palettes.append(dark)

    try:
        for index, palette in enumerate(palettes):
            qapp.setPalette(palette)
            dialog = GuidedFirstSceneEditorDialog(
                settings=_settings(tmp_path, f"palette-{index}.ini")
            )
            qtbot.addWidget(dialog)  # type: ignore[attr-defined]
            _show(dialog, qapp)
            assert dialog.welcome_overlay.isVisible()
            assert "palette(base)" in dialog.welcome_overlay.styleSheet()
            dialog.welcome_overlay.start_button.click()
            qapp.processEvents()
            assert dialog.tour_overlay.isVisible()
            assert "palette(base)" in dialog.tour_overlay.card.styleSheet()
            dialog.close()
    finally:
        qapp.setPalette(original)


def test_beginner_and_expert_modes_preserve_core_workspace(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "mode-consistency.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show(dialog, qapp)
    dialog.welcome_overlay.skip_button.click()
    qapp.processEvents()

    assert dialog.editor_splitter.isVisible()
    assert dialog.documentation_panel.isVisible()
    assert dialog.buttons.isVisible()

    dialog.beginner_mode_checkbox.setChecked(False)
    qapp.processEvents()
    assert not dialog.workflow_panel.isVisible()
    assert dialog.editor_splitter.isVisible()
    assert dialog.documentation_panel.isVisible()
    assert dialog.buttons.isVisible()
    assert dialog.restart_tour_button.isVisible()

    dialog.beginner_mode_checkbox.setChecked(True)
    qapp.processEvents()
    assert dialog.workflow_panel.isVisible()
    assert dialog.editor_splitter.isVisible()
    assert dialog.documentation_panel.isVisible()


def test_validation_status_is_textual_not_colour_only(
    qtbot: object,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "validation-text.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert "blocking issue" in dialog.validation_panel.title_label.text()
    assert dialog.validation_label.text().strip()

    dialog.scene_name_edit.setText("Arrival at Xorix")
    dialog.heading_edit.setText("EXT. XORIX ORBIT - DAY")
    dialog.summary_edit.setPlainText("The crew sees Xorix for the first time.")
    dialog._validate()
    assert "blocking issue" in dialog.validation_panel.title_label.text()

    cancel = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    assert cancel is not None
    assert cancel.text().strip()
