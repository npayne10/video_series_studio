"""Phase 16.2a.8.5.4.5.1 onboarding functional certification."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from tests.certification.certification_matrix import (
    ONBOARDING_FUNCTIONAL_MATRIX,
    certification_areas,
    certification_test_nodes,
)
from tests.certification.certification_runner import CertificationRunner
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.presentation.dialogs.guided_first_scene_editor_dialog import (
    GuidedFirstSceneEditorDialog,
)
from vscs.presentation.onboarding import OnboardingOutcome

EXPECTED_AREAS = (
    "Welcome Experience",
    "Beginner Mode",
    "Guided Tour",
    "Guided Navigation",
    "Guided First Scene",
    "Try It Workflow",
    "Validation",
    "VKF Integration",
    "Adaptive Workspace",
    "Persistence",
    "Recovery",
)


def _settings(tmp_path: Path, name: str = "certification.ini") -> QSettings:
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


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


def _start_guide(
    dialog: GuidedFirstSceneEditorDialog,
    qapp: QApplication,
) -> None:
    dialog.show()
    qapp.processEvents()
    assert dialog.welcome_overlay.isVisible()
    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.tour_overlay.isVisible()


def test_certification_matrix_covers_every_approved_functional_area() -> None:
    assert certification_areas() == EXPECTED_AREAS
    assert len(ONBOARDING_FUNCTIONAL_MATRIX) == len(EXPECTED_AREAS)
    assert all(evidence.test_nodes for evidence in ONBOARDING_FUNCTIONAL_MATRIX)
    assert len(certification_test_nodes()) == len(set(certification_test_nodes()))


def test_certification_matrix_references_existing_regression_files() -> None:
    root = Path(__file__).resolve().parents[2]
    missing: list[str] = []
    for node in certification_test_nodes():
        path_text = node.split("::", maxsplit=1)[0]
        if not (root / path_text).is_file():
            missing.append(path_text)
    assert not missing, f"Missing certification evidence: {sorted(set(missing))}"


def test_certification_runner_requires_all_areas_and_reports_failures() -> None:
    runner = CertificationRunner()
    runner.record("Welcome Experience", passed=True)
    assert not runner.complete
    assert not runner.passed
    assert "NOT RUN" in runner.report()

    for area in EXPECTED_AREAS[1:]:
        runner.record(area, passed=area != "Recovery")
    assert runner.complete
    assert not runner.passed
    assert "Recovery........................ FAIL" in runner.report()
    assert "OVERALL RESULT: FAIL" in runner.report()


def test_certification_runner_reports_complete_pass() -> None:
    runner = CertificationRunner()
    for area in EXPECTED_AREAS:
        runner.record(area, passed=True)
    report = runner.report()
    assert runner.complete
    assert runner.passed
    assert "OVERALL RESULT: PASS" in report
    assert report.count("PASS") == len(EXPECTED_AREAS) + 1


def test_end_to_end_guided_first_scene_certification(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(
        location_assets=(_location(),),
        settings=_settings(tmp_path),
    )
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    _start_guide(dialog, qapp)

    dialog.onboarding.go_to(3)
    qapp.processEvents()
    assert dialog.tour_overlay.try_button.isVisible()
    dialog.tour_overlay.try_button.click()
    qapp.processEvents()

    QTest.keyClicks(dialog.scene_name_edit, "Arrival at Xorix")
    QTest.keyClick(dialog.scene_name_edit, Qt.Key.Key_Tab)
    QTest.keyClicks(dialog.heading_edit, "EXT. XORIX ORBIT - DAY")
    QTest.keyClick(dialog.heading_edit, Qt.Key.Key_Tab)
    qapp.processEvents()

    assert dialog.tour_overlay.isVisible()
    assert dialog.tour_overlay.next_button.isEnabled()
    assert dialog.documentation_panel.topic_id in {"scene.heading", "scene.name"}

    dialog.location_combo.setCurrentIndex(1)
    dialog.summary_edit.setPlainText("The crew sees Xorix for the first time.")
    dialog._validate()
    dialog.onboarding.go_to(dialog.onboarding.sequence.total_steps - 1)
    qapp.processEvents()

    assert dialog.save_button.isEnabled()
    assert dialog.tour_overlay.next_button.text() == "Create Scene"
    dialog.tour_overlay.next_button.click()
    qapp.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.onboarding.state.outcome is OnboardingOutcome.COMPLETED


def test_skip_persistence_and_restart_recovery_certification(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, "persistence.ini")
    first = GuidedFirstSceneEditorDialog(settings=settings)
    qtbot.addWidget(first)  # type: ignore[attr-defined]
    first.show()
    qapp.processEvents()
    assert first.welcome_overlay.isVisible()
    first.welcome_overlay.skip_button.click()
    qapp.processEvents()
    assert first.onboarding.state.outcome is OnboardingOutcome.SKIPPED

    second = GuidedFirstSceneEditorDialog(settings=settings)
    qtbot.addWidget(second)  # type: ignore[attr-defined]
    second.show()
    qapp.processEvents()
    assert not second.welcome_overlay.isVisible()

    second.restart_tour_button.click()
    qapp.processEvents()
    assert second.welcome_overlay.isVisible()
    second.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert second.tour_overlay.isVisible()
    assert second.onboarding.state.active


def test_onboarding_preserves_adaptive_workspace_controls(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = GuidedFirstSceneEditorDialog(settings=_settings(tmp_path, "layout.ini"))
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]
    dialog.show()
    qapp.processEvents()

    assert dialog.workspace_splitter.count() >= 2
    assert dialog.editor_splitter.count() == 2
    assert dialog.workflow_panel.collapsed
    assert dialog.summary_panel.collapsed
    assert dialog.validation_panel.collapsed

    dialog.welcome_overlay.start_button.click()
    qapp.processEvents()
    assert dialog.workspace_splitter.count() >= 2
    assert dialog.editor_splitter.count() == 2
    assert dialog.tour_overlay.isVisible()
