"""CAP gallery integration for the Canonical Image Evaluation Engine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMessageBox, QPushButton

from vscs.application.ciee import CanonicalImageEvaluationEngine, CIEEError
from vscs.domain.caps import CanonicalReferenceType
from vscs.presentation.widgets import cap_manager


def _absolute_path(dialog: Any, relative_or_absolute: Path) -> Path:
    if relative_or_absolute.is_absolute():
        return relative_or_absolute
    return Path(dialog.project_directory) / relative_or_absolute


def _format_report(report: Any, report_path: Path) -> str:
    metrics = "\n".join(
        f"• {metric.name}: {metric.score}/100 — {metric.summary}" for metric in report.metrics
    )
    warnings = "\n".join(f"• {warning}" for warning in report.warnings) or "• None"
    checks = "\n".join(f"• {check}" for check in report.manual_checks)
    return (
        f"Decision: {report.decision.value.upper()}\n"
        f"Overall technical score: {report.overall_score}/100\n"
        f"Image: {report.width} x {report.height}\n\n"
        f"Technical metrics\n{metrics}\n\n"
        f"Warnings\n{warnings}\n\n"
        f"Required visual review\n{checks}\n\n"
        f"Report saved to:\n{report_path}"
    )


def _evaluate_selected(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if reference is None:
        QMessageBox.information(
            dialog, "Canonical Image Evaluation", "Select an image reference first."
        )
        return
    if reference.reference_type is not CanonicalReferenceType.IMAGE:
        QMessageBox.warning(
            dialog, "Canonical Image Evaluation", "CIEE v1.0 evaluates image references only."
        )
        return
    if dialog.profile is None or dialog.project_directory is None:
        return

    try:
        asset = dialog.caps.assets.get(dialog.profile.asset_id)
        image_path = _absolute_path(dialog, reference.file_path)
        report = CanonicalImageEvaluationEngine().evaluate(
            image_path,
            asset_id=dialog.profile.asset_id,
            category=asset.category,
        )
        report_root = (
            Path(dialog.project_directory)
            / "Canonical Assets"
            / dialog.profile.asset_id.upper()
            / ".metadata"
            / "evaluation"
        )
        report_root.mkdir(parents=True, exist_ok=True)
        report_path = report_root / f"{image_path.stem}.ciee.json"
        payload = report.as_dict()
        payload["reference_id"] = reference.id
        payload["reference_title"] = reference.title
        payload["evaluated_at"] = datetime.now(UTC).isoformat()
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except (CIEEError, OSError, ValueError) as exc:
        QMessageBox.critical(dialog, "Canonical Image Evaluation", str(exc))
        return

    box = QMessageBox(dialog)
    box.setWindowTitle("Canonical Image Evaluation")
    box.setIcon(
        QMessageBox.Icon.Information
        if report.decision.value == "pass"
        else QMessageBox.Icon.Warning
    )
    box.setText(f"{reference.title}: {report.decision.value.upper()} ({report.overall_score}/100)")
    box.setDetailedText(_format_report(report, report_path.relative_to(dialog.project_directory)))
    box.setInformativeText(
        "CIEE v1.0 completed deterministic local technical checks. "
        "Prompt adherence, visible text, canon consistency and engineering plausibility "
        "still require the listed visual review."
    )
    box.exec()


def _update_button(dialog: Any) -> None:
    button = getattr(dialog, "evaluate_reference_button", None)
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if button is not None:
        button.setEnabled(
            reference is not None and reference.reference_type is CanonicalReferenceType.IMAGE
        )


def install_canonical_image_evaluation() -> None:
    """Install CIEE controls into the enhanced CAP editor."""
    if getattr(cap_manager.CAPEditorDialog, "_ciee_installed", False):
        return

    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references

    def ciee_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.evaluate_reference_button = QPushButton("Evaluate Selected Image…")
        self.evaluate_reference_button.setObjectName("evaluateCanonicalImageButton")
        self.evaluate_reference_button.setToolTip(
            "Run CIEE technical quality checks and save a versioned evaluation report."
        )
        self.evaluate_reference_button.clicked.connect(lambda: _evaluate_selected(self))
        self.layout().insertWidget(2, self.evaluate_reference_button)
        gallery = getattr(self, "reference_gallery", None)
        if gallery is not None:
            gallery.gallery.currentItemChanged.connect(lambda *_: _update_button(self))
        _update_button(self)

    def ciee_refresh(self: Any) -> None:
        original_refresh(self)
        _update_button(self)

    cap_manager.CAPEditorDialog.__init__ = ciee_init
    cap_manager.CAPEditorDialog._refresh_references = ciee_refresh
    cap_manager.CAPEditorDialog._ciee_installed = True
