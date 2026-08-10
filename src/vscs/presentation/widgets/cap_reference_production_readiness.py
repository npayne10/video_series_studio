"""CAP gallery integration for combined Production Readiness Evaluation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMessageBox, QPushButton

from vscs.application.pre import PREError, ProductionReadinessEngine
from vscs.domain.caps import CanonicalReferenceType
from vscs.presentation.widgets import cap_manager


def _evaluate_production_readiness(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if reference is None:
        QMessageBox.information(dialog, "Production Readiness", "Select an image reference first.")
        return
    if reference.reference_type is not CanonicalReferenceType.IMAGE:
        QMessageBox.warning(dialog, "Production Readiness", "PRE evaluates image references only.")
        return
    if dialog.profile is None or dialog.project_directory is None:
        return

    project_root = Path(dialog.project_directory)
    image_path = (
        reference.file_path
        if reference.file_path.is_absolute()
        else project_root / reference.file_path
    )
    report_root = (
        project_root
        / "Canonical Assets"
        / dialog.profile.asset_id.upper()
        / ".metadata"
        / "evaluation"
    )
    ciee_path = report_root / f"{image_path.stem}.ciee.json"
    siee_path = report_root / f"{image_path.stem}.siee.json"

    missing = [path.name for path in (ciee_path, siee_path) if not path.is_file()]
    if missing:
        QMessageBox.warning(
            dialog,
            "Production Readiness",
            "PRE requires both technical and semantic evaluations. Run CIEE and SIEE first.\n\n"
            + "Missing: "
            + ", ".join(missing),
        )
        return

    try:
        report = ProductionReadinessEngine().evaluate(
            image_path=image_path,
            asset_id=dialog.profile.asset_id,
            reference_id=reference.id,
            technical_report_path=ciee_path,
            semantic_report_path=siee_path,
            locked=reference.locked,
        )
        report_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(UTC)
        latest_path = report_root / f"{image_path.stem}.pre.json"
        history_path = (
            report_root / f"{image_path.stem}.{timestamp.strftime('%Y%m%dT%H%M%S%fZ')}.pre.json"
        )
        payload = report.as_dict()
        payload.update(
            {
                "reference_title": reference.title,
                "evaluated_at": timestamp.isoformat(),
            }
        )
        encoded = json.dumps(payload, indent=2, sort_keys=True)
        latest_path.write_text(encoded, encoding="utf-8")
        history_path.write_text(encoded, encoding="utf-8")
    except (PREError, OSError, ValueError) as exc:
        QMessageBox.critical(dialog, "Production Readiness", str(exc))
        return

    recommendations = "\n".join(f"• {item}" for item in report.recommendations) or "• None"
    blockers = "\n".join(f"• {item}" for item in report.blocking_reasons) or "• None"
    details = (
        f"Decision: {report.decision.value.upper()}\n"
        f"Production readiness: {report.overall_score}/100\n"
        f"Technical: {report.technical_score}/100\n"
        f"Semantic: {report.semantic_score}/100\n"
        f"Canon consistency: {report.canon_score}/100\n"
        f"Canon risk: {report.canon_risk.value.upper()}\n"
        f"Readiness state: {report.readiness_state.value.replace('_', ' ').title()}\n\n"
        f"Blocking reasons\n{blockers}\n\n"
        f"Recommendations\n{recommendations}\n\n"
        f"Latest report\n{latest_path.relative_to(project_root)}\n\n"
        f"History report\n{history_path.relative_to(project_root)}"
    )

    box = QMessageBox(dialog)
    box.setWindowTitle("Production Readiness Evaluation")
    box.setIcon(
        QMessageBox.Icon.Information
        if report.decision.value == "pass"
        else QMessageBox.Icon.Warning
    )
    box.setText(
        f"{reference.title}: {report.decision.value.upper()} "
        f"({report.overall_score}/100 production readiness)"
    )
    box.setInformativeText(
        f"Canon risk: {report.canon_risk.value.upper()} · "
        f"State: {report.readiness_state.value.replace('_', ' ').title()}"
    )
    box.setDetailedText(details)
    box.exec()


def _update_button(dialog: Any) -> None:
    button = getattr(dialog, "production_readiness_button", None)
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if button is not None:
        button.setEnabled(
            reference is not None and reference.reference_type is CanonicalReferenceType.IMAGE
        )


def install_production_readiness_evaluation() -> None:
    """Install PRE controls into the enhanced CAP editor."""
    if getattr(cap_manager.CAPEditorDialog, "_pre_installed", False):
        return

    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references

    def pre_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.production_readiness_button = QPushButton("Production Readiness…")
        self.production_readiness_button.setObjectName("productionReadinessButton")
        self.production_readiness_button.setToolTip(
            "Combine the latest CIEE and SIEE reports into a production-readiness decision."
        )
        self.production_readiness_button.clicked.connect(
            lambda: _evaluate_production_readiness(self)
        )
        self.layout().insertWidget(2, self.production_readiness_button)
        gallery = getattr(self, "reference_gallery", None)
        if gallery is not None:
            gallery.gallery.currentItemChanged.connect(lambda *_: _update_button(self))
        _update_button(self)

    def pre_refresh(self: Any) -> None:
        original_refresh(self)
        _update_button(self)

    cap_manager.CAPEditorDialog.__init__ = pre_init
    cap_manager.CAPEditorDialog._refresh_references = pre_refresh
    cap_manager.CAPEditorDialog._pre_installed = True
