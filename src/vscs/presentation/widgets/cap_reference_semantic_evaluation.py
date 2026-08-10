"""CAP gallery integration for semantic image evaluation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMessageBox, QPushButton

from vscs.application.siee import SemanticImageEvaluationEngine, SIEEError
from vscs.domain.caps import (
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)
from vscs.infrastructure.ai import AICredentialStore
from vscs.infrastructure.ai.openai_semantic_evaluator import OpenAISemanticImageEvaluator
from vscs.infrastructure.configuration import ConfigurationService
from vscs.presentation.widgets import cap_manager


def _absolute(dialog: Any, path: Path) -> Path:
    return path if path.is_absolute() else Path(dialog.project_directory) / path


def _approved_primary(dialog: Any, selected_id: int) -> Path | None:
    if dialog.profile is None or dialog.reference_service is None:
        return None
    for reference in dialog.reference_service.list_for_cap(dialog.profile.asset_id):
        if (
            reference.id != selected_id
            and reference.reference_type is CanonicalReferenceType.IMAGE
            and reference.role is CanonicalReferenceRole.PRIMARY
            and reference.status is CanonicalReferenceStatus.APPROVED
        ):
            path = _absolute(dialog, reference.file_path)
            return path if path.is_file() else None
    return None


def _format_report(report: Any, report_path: Path) -> str:
    metrics = "\n".join(
        f"• {metric.name}: {metric.score}/100{' [BLOCKING]' if metric.blocking else ''}\n  {metric.summary}"
        + ("\n  Evidence: " + "; ".join(metric.evidence) if metric.evidence else "")
        for metric in report.metrics
    )
    features = "\n".join(f"• {item}" for item in report.detected_features) or "• None listed"
    violations = "\n".join(f"• {item}" for item in report.violations) or "• None"
    recommendations = "\n".join(f"• {item}" for item in report.recommendations) or "• None"
    return (
        f"Decision: {report.decision.value.upper()}\n"
        f"Overall semantic score: {report.overall_score}/100\n"
        f"Provider: {report.provider}\nModel: {report.model}\n"
        f"Primary reference comparison: {'Yes' if report.primary_reference_path else 'No'}\n\n"
        f"Semantic metrics\n{metrics}\n\nDetected features\n{features}\n\n"
        f"Violations\n{violations}\n\nRecommendations\n{recommendations}\n\n"
        f"Summary\n{report.summary}\n\nReport saved to:\n{report_path}"
    )


def _evaluate_selected(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if reference is None or reference.reference_type is not CanonicalReferenceType.IMAGE:
        QMessageBox.information(
            dialog, "Semantic Image Evaluation", "Select an image reference first."
        )
        return
    if dialog.profile is None or dialog.project_directory is None:
        return

    try:
        configuration = ConfigurationService()
        configuration.load()
        api_key = AICredentialStore().get_openai_api_key()
        if not api_key:
            raise SIEEError(
                "Configure an OpenAI API key in VSCS Settings before running semantic evaluation."
            )
        model = configuration.settings.ai.openai_model
        provider = OpenAISemanticImageEvaluator(api_key=api_key, model=model)
        asset = dialog.caps.assets.get(dialog.profile.asset_id)
        image_path = _absolute(dialog, reference.file_path)
        primary_path = _approved_primary(dialog, reference.id)
        report = SemanticImageEvaluationEngine(provider).evaluate(
            image_path,
            asset_id=asset.asset_id,
            asset_name=asset.name,
            category=asset.category,
            canonical_description=dialog.profile.canonical_description,
            visual_identity=dialog.profile.visual_identity,
            production_notes=dialog.profile.production_notes,
            generation_prompt=reference.description,
            primary_reference_path=primary_path,
        )
        report_root = (
            Path(dialog.project_directory)
            / "Canonical Assets"
            / dialog.profile.asset_id.upper()
            / ".metadata"
            / "evaluation"
        )
        report_root.mkdir(parents=True, exist_ok=True)
        report_path = report_root / f"{image_path.stem}.siee.json"
        payload = report.as_dict()
        payload.update(
            {
                "reference_id": reference.id,
                "reference_title": reference.title,
                "evaluated_at": datetime.now(UTC).isoformat(),
            }
        )
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except (SIEEError, OSError, ValueError, RuntimeError) as exc:
        QMessageBox.critical(dialog, "Semantic Image Evaluation", str(exc))
        return

    box = QMessageBox(dialog)
    box.setWindowTitle("Semantic Image Evaluation")
    box.setIcon(
        QMessageBox.Icon.Information
        if report.decision.value == "pass"
        else QMessageBox.Icon.Warning
    )
    box.setText(
        f"{reference.title}: {report.decision.value.upper()} ({report.overall_score}/100 semantic)"
    )
    box.setInformativeText(report.summary)
    box.setDetailedText(_format_report(report, report_path.relative_to(dialog.project_directory)))
    box.exec()


def _update_button(dialog: Any) -> None:
    button = getattr(dialog, "semantic_evaluate_button", None)
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if button is not None:
        button.setEnabled(
            reference is not None and reference.reference_type is CanonicalReferenceType.IMAGE
        )


def install_semantic_image_evaluation() -> None:
    """Install SIEE controls into the enhanced CAP editor."""
    if getattr(cap_manager.CAPEditorDialog, "_siee_installed", False):
        return
    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references

    def siee_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.semantic_evaluate_button = QPushButton("Semantic Evaluate Selected…")
        self.semantic_evaluate_button.setObjectName("semanticEvaluateCanonicalImageButton")
        self.semantic_evaluate_button.setToolTip(
            "Use a configured vision-capable OpenAI model to evaluate prompt adherence, category, text, canon, engineering and cinematic quality."
        )
        self.semantic_evaluate_button.clicked.connect(lambda: _evaluate_selected(self))
        self.layout().insertWidget(3, self.semantic_evaluate_button)
        gallery = getattr(self, "reference_gallery", None)
        if gallery is not None:
            gallery.gallery.currentItemChanged.connect(lambda *_: _update_button(self))
        _update_button(self)

    def siee_refresh(self: Any) -> None:
        original_refresh(self)
        _update_button(self)

    cap_manager.CAPEditorDialog.__init__ = siee_init
    cap_manager.CAPEditorDialog._refresh_references = siee_refresh
    cap_manager.CAPEditorDialog._siee_installed = True
