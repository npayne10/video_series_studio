"""Phase 16.2a.8.5.4.5.2.3 overlay and spotlight certification."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication, QFrame, QWidget

from tests.certification.overlay_spotlight_matrix import (
    OVERLAY_SPOTLIGHT_MATRIX,
    overlay_spotlight_areas,
    overlay_spotlight_test_nodes,
)
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)
from vscs.presentation.onboarding import (
    GuidedTourOverlay,
    OnboardingController,
    OnboardingSequence,
    OnboardingStep,
)

EXPECTED_AREAS = (
    "Welcome overlay coverage",
    "Tour overlay coverage",
    "Spotlight target accuracy",
    "Card collision avoidance",
    "Missing target recovery",
    "Scrolling and spotlight refresh",
    "Focus-safe redraw",
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


def _test_state(tmp_path: Path) -> tuple[OnboardingController, QSettings]:
    settings = _settings(tmp_path, "overlay-state.ini")
    sequence = OnboardingSequence(
        guide_id="overlay-certification",
        title="Overlay certification",
        version=1,
        steps=(OnboardingStep("target", "Target", "Highlight the target."),),
    )
    controller = OnboardingController(sequence, settings)
    controller.start()
    return controller, settings


def test_overlay_spotlight_matrix_covers_every_approved_area() -> None:
    assert overlay_spotlight_areas() == EXPECTED_AREAS
    assert len(OVERLAY_SPOTLIGHT_MATRIX) == len(EXPECTED_AREAS)
    nodes = overlay_spotlight_test_nodes()
    assert len(nodes) == len(set(nodes))


def test_overlay_spotlight_matrix_references_existing_test_files() -> None:
    root = Path(__file__).resolve().parents[2]
    missing = {
        node.split("::", maxsplit=1)[0]
        for node in overlay_spotlight_test_nodes()
        if not (root / node.split("::", maxsplit=1)[0]).is_file()
    }
    assert not missing


def test_welcome_overlay_covers_dialog_and_card_stays_inside(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "welcome.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.resize(900, 680)
    _show(dialog, qapp)

    card = dialog.welcome_overlay.findChild(QFrame, "onboardingWelcomeCard")
    assert card is not None
    assert dialog.welcome_overlay.geometry() == dialog.rect()
    assert dialog.welcome_overlay.rect().contains(card.geometry())

    dialog.resize(1450, 920)
    qapp.processEvents()
    assert dialog.welcome_overlay.geometry() == dialog.rect()
    assert dialog.welcome_overlay.rect().contains(card.geometry())


def test_tour_overlay_covers_dialog_after_resize(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "tour.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.resize(900, 680)
    _start_guide(dialog, qapp)

    assert dialog.tour_overlay.geometry() == dialog.rect()
    assert dialog.tour_overlay.rect().contains(dialog.tour_overlay.card.geometry())

    dialog.resize(1500, 950)
    qapp.processEvents()
    assert dialog.tour_overlay.geometry() == dialog.rect()
    assert dialog.tour_overlay.rect().contains(dialog.tour_overlay.card.geometry())


def test_spotlight_contains_the_navigated_target(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "accuracy.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)
    dialog.onboarding.go_to(1)
    qapp.processEvents()

    target = dialog.workflow_navigator.target("production_type")
    assert target is not None
    target_center_global = target.mapToGlobal(target.rect().center())
    target_center_overlay = dialog.tour_overlay.mapFromGlobal(target_center_global)
    assert not dialog.tour_overlay.spotlight_rect.isNull()
    assert dialog.tour_overlay.spotlight_rect.contains(target_center_overlay)


def test_tour_card_avoids_a_top_right_spotlight(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    parent = QWidget()
    parent.resize(900, 700)
    qtbot.addWidget(parent)  # type: ignore[attr-defined]
    target = QWidget(parent)
    target.setGeometry(590, 20, 270, 110)
    target.show()
    overlay = GuidedTourOverlay(parent)
    controller, _settings_object = _test_state(tmp_path)

    parent.show()
    qapp.processEvents()
    overlay.show_state(controller.state, target)
    qapp.processEvents()

    assert overlay.isVisible()
    assert not overlay.card.geometry().intersects(overlay.spotlight_rect)
    assert overlay.card.y() > parent.height() // 2


def test_missing_or_hidden_target_clears_spotlight_safely(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    parent = QWidget()
    parent.resize(900, 700)
    qtbot.addWidget(parent)  # type: ignore[attr-defined]
    overlay = GuidedTourOverlay(parent)
    controller, _settings_object = _test_state(tmp_path)
    hidden = QWidget(parent)
    hidden.hide()

    parent.show()
    qapp.processEvents()
    overlay.show_state(controller.state, None)
    assert overlay.spotlight_rect.isNull()
    assert overlay.rect().contains(overlay.card.geometry())

    overlay.show_state(controller.state, hidden)
    assert overlay.spotlight_rect.isNull()
    assert overlay.rect().contains(overlay.card.geometry())


def test_spotlight_tracks_target_after_guided_scrolling(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "scrolling.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.resize(900, 680)
    _start_guide(dialog, qapp)
    dialog.onboarding.go_to(8)
    qapp.processEvents()

    target = dialog.workflow_navigator.target("production")
    assert target is not None
    target_center_global = target.mapToGlobal(target.rect().center())
    target_center_overlay = dialog.tour_overlay.mapFromGlobal(target_center_global)
    assert dialog.tour_overlay.spotlight_rect.contains(target_center_overlay)
    viewport_rect = dialog.scroll_area.viewport().rect()
    target_top_left = dialog.scroll_area.viewport().mapFromGlobal(
        target.mapToGlobal(QPoint(0, 0))
    )
    assert viewport_rect.adjusted(-20, -20, 20, 20).contains(target_top_left)


def test_overlay_resize_keeps_tour_focus_and_geometry(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        settings=_settings(tmp_path, "focus-redraw.ini")
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)
    assert dialog.tour_overlay.next_button.hasFocus()

    for width, height in ((800, 640), (1400, 900), (1024, 700)):
        dialog.resize(width, height)
        qapp.processEvents()
        assert dialog.tour_overlay.geometry() == dialog.rect()
        assert dialog.tour_overlay.rect().contains(dialog.tour_overlay.card.geometry())
        assert dialog.tour_overlay.next_button.hasFocus()
