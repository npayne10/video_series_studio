"""Phase 19.4.10/19.4.11 Production Review UI tests."""

from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from vscs.application.production_package_review import (
    ProductionPackageReview,
    ReviewStatus,
)
from vscs.presentation.widgets.production_package_review_workspace import (
    _build_tab,
    _render,
)


class _Acceptance:
    def __init__(self, accepted: bool) -> None:
        self.accepted = accepted

    def assess(self, _shot_id: str, _provider_id: str):
        failed = () if self.accepted else (
            SimpleNamespace(
                passed=False,
                message="Final human approval is not recorded.",
            ),
        )
        return SimpleNamespace(accepted=self.accepted, checks=failed)


def test_production_review_tab_exposes_final_human_gate(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    workspace = SimpleNamespace(compiler_tabs=QTabWidget(parent))

    _build_tab(workspace)

    assert workspace.compiler_tabs.count() == 1
    assert workspace.compiler_tabs.tabText(0) == "Production Review"
    assert workspace.production_review_validate_button.text() == "Validate Package"
    assert workspace.production_review_approve_button.text() == "Approve for Production"
    assert workspace.production_review_changes_button.text() == "Request Changes"
    assert workspace.production_acceptance_status.text() == ""


def test_review_render_enables_approval_only_after_validation_pass(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    workspace = SimpleNamespace(
        production_review_status=QLabel(parent),
        production_acceptance_status=QLabel(parent),
        production_review_summary=QTextEdit(parent),
        production_review_reviewer=QLineEdit(parent),
        production_review_notes=QTextEdit(parent),
        production_review_approve_button=QPushButton(parent),
        production_review_changes_button=QPushButton(parent),
        production_acceptance_service=_Acceptance(False),
    )
    review = ProductionPackageReview(
        shot_id="SHT-001",
        provider_id="comfyui",
        status=ReviewStatus.REVIEW_REQUIRED,
        validation_passed=True,
        findings=(),
        dependency_fingerprint="fingerprint",
        canonical_reference_count=4,
        asset_count=4,
        provider_contract="vscs.comfyui.production-input.v1",
        provider_execution="not-submitted",
        reviewed_at="2026-08-13T00:00:00+00:00",
    )

    _render(workspace, review, False)

    assert "VALIDATION PASS" in workspace.production_review_status.text()
    assert "PHASE 19.4 NOT READY" in workspace.production_acceptance_status.text()
    assert workspace.production_review_approve_button.isEnabled()
    assert "Canonical references: 4" in workspace.production_review_summary.toPlainText()


def test_review_render_shows_phase_19_4_accepted_after_final_gate(qtbot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    workspace = SimpleNamespace(
        production_review_status=QLabel(parent),
        production_acceptance_status=QLabel(parent),
        production_review_summary=QTextEdit(parent),
        production_review_reviewer=QLineEdit(parent),
        production_review_notes=QTextEdit(parent),
        production_review_approve_button=QPushButton(parent),
        production_review_changes_button=QPushButton(parent),
        production_acceptance_service=_Acceptance(True),
    )
    review = ProductionPackageReview(
        shot_id="SHT-001",
        provider_id="comfyui",
        status=ReviewStatus.APPROVED,
        validation_passed=True,
        findings=(),
        dependency_fingerprint="fingerprint",
        canonical_reference_count=4,
        asset_count=4,
        provider_contract="vscs.comfyui.production-input.v1",
        provider_execution="not-submitted",
        reviewed_at="2026-08-13T00:00:00+00:00",
        reviewed_by="Neill",
    )

    _render(workspace, review, True)

    assert "APPROVED FOR PRODUCTION" in workspace.production_review_status.text()
    assert "PHASE 19.4 ACCEPTED" in workspace.production_acceptance_status.text()
    assert not workspace.production_review_approve_button.isEnabled()
