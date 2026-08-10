"""Phase 16.2a.8.5.4.5.2.1 responsive layout certification."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QFrame

from tests.certification.responsive_layout_matrix import (
    RESPONSIVE_LAYOUT_MATRIX,
    responsive_layout_areas,
    responsive_layout_test_nodes,
)
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)

EXPECTED_AREAS = (
    "Compact laptop layout",
    "Standard desktop layout",
    "Large desktop layout",
    "Live resize",
    "Welcome overlay fit",
    "Tour overlay fit",
    "Responsive persistence",
)


def _settings(tmp_path: Path, name: str) -> QSettings:
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


def _show_at(
    dialog: GuidedFirstSceneEditorDialog,
    qapp: QApplication,
    width: int,
    height: int,
) -> None:
    dialog.resize(width, height)
    dialog.show()
    qapp.processEvents()


def test_responsive_matrix_covers_every_approved_layout_area() -> None:
    assert responsive_layout_areas() == EXPECTED_AREAS
    assert len(RESPONSIVE_LAYOUT_MATRIX) == len(EXPECTED_AREAS)
    assert len(responsive_layout_test_nodes()) == len(set(responsive_layout_test_nodes()))


def test_responsive_matrix_references_existing_test_file() -> None:
    root = Path(__file__).resolve().parents[2]
    missing = {
        node.split("::", maxsplit=1)[0]
        for node in responsive_layout_test_nodes()
        if not (root / node.split("::", maxsplit=1)[0]).is_file()
    }
    assert not missing


def test_compact_layout_keeps_editor_scrollable_and_actions_visible(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "compact.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show_at(dialog, qapp, 800, 640)

    cancel_button = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
    assert dialog.width() >= 760
    assert dialog.height() >= 620
    assert dialog.workspace_splitter.isVisible()
    assert dialog.editor_splitter.isVisible()
    assert dialog.scroll_area.isVisible()
    assert dialog.scroll_area.verticalScrollBar().maximum() > 0
    assert dialog.buttons.isVisible()
    assert dialog.save_button.isVisible()
    assert cancel_button is not None
    assert cancel_button.isVisible()


def test_standard_layout_prioritises_the_editor(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "standard.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show_at(dialog, qapp, 1100, 760)

    workflow, editor, support = dialog.workspace_splitter.sizes()
    assert dialog.workflow_panel.collapsed
    assert dialog.summary_panel.collapsed
    assert dialog.validation_panel.collapsed
    assert editor > workflow
    assert editor > support
    assert editor > (workflow + support)


def test_large_layout_preserves_compact_support_panels(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "large.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show_at(dialog, qapp, 1600, 1000)

    sizes = dialog.workspace_splitter.sizes()
    assert dialog.workflow_panel.collapsed
    assert dialog.summary_panel.collapsed
    assert dialog.validation_panel.collapsed
    assert sizes[1] == max(sizes)
    assert dialog.editor_splitter.sizes()[0] > 0
    assert dialog.editor_splitter.sizes()[1] > 0


def test_live_resize_preserves_workspace_structure(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "resize.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show_at(dialog, qapp, 1100, 760)

    for width, height in ((800, 640), (1400, 900), (1024, 700), (1600, 1000)):
        dialog.resize(width, height)
        qapp.processEvents()
        assert dialog.workspace_splitter.count() == 3
        assert dialog.support_splitter.count() == 2
        assert dialog.editor_splitter.count() == 2
        assert dialog.workspace_splitter.sizes()[1] > 0
        assert dialog.buttons.isVisible()
        assert dialog.save_button.isVisible()


def test_welcome_overlay_tracks_dialog_geometry(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "welcome.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show_at(dialog, qapp, 900, 680)

    assert dialog.welcome_overlay.isVisible()
    assert dialog.welcome_overlay.geometry() == dialog.rect()
    card = dialog.welcome_overlay.findChild(QFrame, "onboardingWelcomeCard")
    assert card is not None
    assert dialog.welcome_overlay.rect().contains(card.geometry())

    dialog.resize(1400, 900)
    qapp.processEvents()
    assert dialog.welcome_overlay.geometry() == dialog.rect()
    assert dialog.welcome_overlay.rect().contains(card.geometry())


def test_tour_overlay_and_card_fit_resized_dialog(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "tour.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _show_at(dialog, qapp, 900, 680)
    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()

    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.geometry() == dialog.rect()
    assert dialog.tour_overlay.rect().contains(dialog.tour_overlay.card.geometry())

    dialog.resize(1500, 950)
    qapp.processEvents()
    assert dialog.tour_overlay.geometry() == dialog.rect()
    assert dialog.tour_overlay.rect().contains(dialog.tour_overlay.card.geometry())


def test_responsive_layout_state_restores_at_a_different_window_size(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, "persistence.ini")
    first = GuidedFirstSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    _show_at(first, qapp, 1400, 900)
    first.workflow_panel.set_collapsed(False)
    first.summary_panel.set_collapsed(True)
    first.validation_panel.set_collapsed(False)
    first.workspace_splitter.setSizes([180, 560, 160])
    first.editor_splitter.setSizes([850, 350])
    first._save_adaptive_workspace()

    second = GuidedFirstSceneEditorDialog(settings=settings)
    qtbot.addWidget(second)  # type: ignore[attr-defined]
    _show_at(second, qapp, 900, 680)

    assert not second.workflow_panel.collapsed
    assert second.summary_panel.collapsed
    assert not second.validation_panel.collapsed
    assert second.workspace_splitter.count() == 3
    assert second.editor_splitter.count() == 2
    assert second.workspace_splitter.sizes()[1] > 0
    assert second.editor_splitter.sizes()[0] > second.editor_splitter.sizes()[1]
    assert second.buttons.isVisible()
