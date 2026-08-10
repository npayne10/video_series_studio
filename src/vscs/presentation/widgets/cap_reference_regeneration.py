"""Regenerate canonical candidates from PRE and SIEE evaluation feedback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QMessageBox, QPushButton

from vscs.application.caps.asset_generator import (
    CanonicalAssetGenerationError,
    CanonicalAssetGeneratorService,
)
from vscs.application.caps.reference_service import CanonicalReferenceError
from vscs.domain.caps import CanonicalAssetGenerationRequest, CanonicalReferenceType
from vscs.infrastructure.xcic import XCICImageProvider
from vscs.presentation.widgets import cap_manager


class FeedbackRegenerationError(RuntimeError):
    """Raised when evaluation-driven regeneration cannot be prepared."""


def _absolute_path(dialog: Any, path: Path) -> Path:
    return path if path.is_absolute() else Path(dialog.project_directory) / path


def _metadata_paths(dialog: Any, reference: Any) -> tuple[Path, Path, Path]:
    project_root = Path(dialog.project_directory)
    image_path = _absolute_path(dialog, reference.file_path)
    metadata_root = (
        project_root / "Canonical Assets" / dialog.profile.asset_id.upper() / ".metadata"
    )
    return (
        metadata_root / "evaluation" / f"{image_path.stem}.pre.json",
        metadata_root / "evaluation" / f"{image_path.stem}.siee.json",
        metadata_root / "generation" / f"{image_path.stem}.generation.json",
    )


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FeedbackRegenerationError(f"Missing {label}: {path.name}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedbackRegenerationError(f"Unable to read {label} {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise FeedbackRegenerationError(f"Invalid {label}: {path.name}")
    return payload


def _feedback(pre: dict[str, Any], siee: dict[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for source in (pre.get("recommendations", []), siee.get("recommendations", [])):
        if isinstance(source, list):
            values.extend(str(item).strip() for item in source if str(item).strip())
    violations = siee.get("violations", [])
    if isinstance(violations, list):
        values.extend(
            f"Correct this detected violation: {item}" for item in violations if str(item).strip()
        )
    return tuple(dict.fromkeys(values))


def _request_from_manifest(manifest: dict[str, Any]) -> CanonicalAssetGenerationRequest:
    try:
        previous_seed = int(manifest.get("seed", 0))
        return CanonicalAssetGenerationRequest(
            prompt=str(manifest.get("prompt", "Evaluation-feedback regeneration")),
            negative_prompt=str(manifest.get("negative_prompt", "")),
            model=str(manifest.get("model", "Qwen Image 2512 via XCIC")),
            seed=max(0, previous_seed + 1),
            width=int(manifest.get("width", 1664)),
            height=int(manifest.get("height", 928)),
            variations=1,
        )
    except (TypeError, ValueError) as exc:
        raise FeedbackRegenerationError(f"Generation provenance is incomplete: {exc}") from exc


def _regenerate(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if reference is None:
        QMessageBox.information(
            dialog, "Regenerate from Feedback", "Select an image reference first."
        )
        return
    if reference.reference_type is not CanonicalReferenceType.IMAGE:
        QMessageBox.warning(
            dialog, "Regenerate from Feedback", "Only image references can be regenerated."
        )
        return
    if (
        dialog.profile is None
        or dialog.project_directory is None
        or dialog.reference_service is None
    ):
        return

    try:
        pre_path, siee_path, generation_path = _metadata_paths(dialog, reference)
        pre = _load_json(pre_path, "PRE report")
        siee = _load_json(siee_path, "SIEE report")
        generation = _load_json(generation_path, "generation manifest")
        feedback = _feedback(pre, siee)
        if not feedback:
            raise FeedbackRegenerationError(
                "The PRE and SIEE reports contain no regeneration recommendations."
            )
        request = _request_from_manifest(generation)
    except FeedbackRegenerationError as exc:
        QMessageBox.warning(dialog, "Regenerate from Feedback", str(exc))
        return

    preview = "\n".join(f"• {item}" for item in feedback)
    if (
        QMessageBox.question(
            dialog,
            "Regenerate from Evaluation Feedback",
            f"Create a new Candidate from '{reference.title}' using these corrections?\n\n"
            f"{preview}\n\n"
            f"The original image and reports will remain unchanged. A new seed ({request.seed}) "
            "will be used and lineage will be recorded.",
        )
        is not QMessageBox.StandardButton.Yes
    ):
        return

    try:
        generator = CanonicalAssetGeneratorService(
            dialog.reference_service,
            XCICImageProvider(Path(dialog.project_directory)),
        )
        created = generator.generate(
            dialog.profile.asset_id,
            request,
            refinement_instructions=feedback,
            parent_reference_id=reference.id,
            parent_generation_manifest=generation_path.relative_to(dialog.project_directory),
        )
    except (CanonicalAssetGenerationError, CanonicalReferenceError, OSError, ValueError) as exc:
        QMessageBox.critical(dialog, "Regenerate from Feedback", str(exc))
        return

    dialog._refresh_references()
    QMessageBox.information(
        dialog,
        "Regenerate from Feedback",
        f"Generated {len(created)} new Candidate reference(s).\n\n"
        "CAIE applied the PRE/SIEE recommendations, XCIC rendered with a new seed, and "
        "the parent-reference lineage was stored in the generation manifest.",
    )


def _update_button(dialog: Any) -> None:
    button = getattr(dialog, "regenerate_feedback_button", None)
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    if button is None:
        return
    enabled = False
    if (
        reference is not None
        and reference.reference_type is CanonicalReferenceType.IMAGE
        and dialog.profile is not None
        and dialog.project_directory is not None
    ):
        pre_path, siee_path, generation_path = _metadata_paths(dialog, reference)
        enabled = pre_path.is_file() and siee_path.is_file() and generation_path.is_file()
    button.setEnabled(enabled)


def install_feedback_regeneration() -> None:
    """Install PRE/SIEE feedback regeneration into the enhanced CAP editor."""
    if getattr(cap_manager.CAPEditorDialog, "_feedback_regeneration_installed", False):
        return

    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references

    def regeneration_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.regenerate_feedback_button = QPushButton("Regenerate from Feedback…")
        self.regenerate_feedback_button.setObjectName("regenerateFromFeedbackButton")
        self.regenerate_feedback_button.setToolTip(
            "Create a new Candidate using the latest PRE and SIEE recommendations."
        )
        self.regenerate_feedback_button.clicked.connect(lambda: _regenerate(self))
        self.layout().insertWidget(2, self.regenerate_feedback_button)
        gallery = getattr(self, "reference_gallery", None)
        if gallery is not None:
            gallery.gallery.currentItemChanged.connect(lambda *_: _update_button(self))
        _update_button(self)

    def regeneration_refresh(self: Any) -> None:
        original_refresh(self)
        _update_button(self)

    cap_manager.CAPEditorDialog.__init__ = regeneration_init
    cap_manager.CAPEditorDialog._refresh_references = regeneration_refresh
    cap_manager.CAPEditorDialog._feedback_regeneration_installed = True
