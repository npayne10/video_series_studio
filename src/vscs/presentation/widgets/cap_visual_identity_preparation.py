"""B.5.26 read-only CAP visual identity and MASTER candidate preparation UI."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.application.caps.reference_templates import CategoryReferenceTemplateService
from vscs.application.caps.visual_identity_preparation import (
    VisualIdentityPreparation,
    prepare_visual_identity,
)


class VisualIdentityPreparationDialog(QDialog):
    """Inspect candidate preparation; deliberately no image or CAP write actions."""

    def __init__(
        self, preparation: VisualIdentityPreparation, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.preparation = preparation
        self.setWindowTitle(f"Prepare MASTER Candidate (Offline) — {preparation.title}")
        self.setMinimumSize(850, 680)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setObjectName("visualIdentityPreparationScroll")
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        status = (
            "BLOCKED — cannot prepare image generation"
            if preparation.blockers
            else "READY FOR HUMAN-REVIEWED MASTER CANDIDATE GENERATION — not approved"
        )
        self.status_label = QLabel(status)
        self.status_label.setObjectName("visualIdentityPreparationStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        form = QFormLayout()
        form.addRow("Asset", QLabel(f"{preparation.asset_id} — {preparation.category.value}"))
        form.addRow("Default execution preference", QLabel("Local / ComfyUI; no provider called"))
        form.addRow(
            "Source fingerprint", QLabel(preparation.specification_fingerprint or "Missing")
        )
        form.addRow(
            "Decision audit fingerprint", QLabel(preparation.review_fingerprint or "Missing")
        )
        required = ", ".join(view.value for view in preparation.required_reference_views)
        missing = ", ".join(view.value for view in preparation.missing_reference_views)
        form.addRow("Category-required views", QLabel(required or "(none)"))
        form.addRow("Missing reference views", QLabel(missing or "(none)"))
        layout.addLayout(form)

        def readonly(title: str, value: str, object_name: str) -> QPlainTextEdit:
            label = QLabel(title)
            layout.addWidget(label)
            control = QPlainTextEdit()
            control.setObjectName(object_name)
            control.setReadOnly(True)
            control.setPlainText(value)
            layout.addWidget(control, 1)
            return control

        self.blockers_view = readonly(
            "Unresolved preparation blockers",
            "\n".join(preparation.blockers) or "(none)",
            "visualIdentityPreparationBlockers",
        )
        readonly(
            "Reviewed Draft design fields",
            "\n".join(f"{key}: {value}" for key, value in preparation.accepted_fields)
            or "(none)",
            "visualIdentityReviewedFields",
        )
        readonly(
            "Deferred / rejected design fields (not physical authority)",
            "\n".join(preparation.deferred_fields) or "(none)",
            "visualIdentityDeferredFields",
        )
        readonly(
            "Cross-asset continuity (context only, not a substitute for physical identity)",
            "\n".join(preparation.continuity_context) or "(none)",
            "visualIdentityContinuityContext",
        )
        readonly(
            "Related canonical asset IDs (reference-only)",
            "\n".join(preparation.dependency_asset_ids) or "(none)",
            "visualIdentityRelatedAssets",
        )
        self.prompt_view = readonly(
            "Provider-neutral proposed MASTER prompt (not an approved reference)",
            preparation.master_candidate_prompt,
            "visualIdentityMasterPrompt",
        )
        self.negative_view = readonly(
            "Negative prompt", preparation.negative_prompt, "visualIdentityNegativePrompt"
        )
        self.copy_button = QPushButton("Copy Proposed MASTER Prompt")
        self.copy_button.setObjectName("copyVisualIdentityMasterPrompt")
        self.copy_button.setEnabled(preparation.ready_for_master_candidate)
        self.copy_button.clicked.connect(self._copy_prompt)
        layout.addWidget(self.copy_button)
        note = QLabel(
            "Preparation is offline, makes zero paid/provider calls, and does not create "
            "images, candidate references, approved Canon or Production Approval. "
            "Resolve blockers through a reviewed CAP design decision before continuing. "
            "Once an approved MASTER is locked, use Generate Production References "
            "for MASTER-conditioned derived views."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def _copy_prompt(self) -> None:
        if self.preparation.ready_for_master_candidate:
            QApplication.clipboard().setText(self.prompt_view.toPlainText())


def install_visual_identity_preparation(cap_manager: QWidget) -> QPushButton | None:
    """Integrate B.5.26 into Canonical Profiles using existing CAP reference services."""
    references = getattr(cap_manager, "references", None)
    caps = getattr(cap_manager, "caps", None)
    if references is None or caps is None:
        return None
    library = ReferenceLibraryService(references)
    templates = CategoryReferenceTemplateService(references, library)
    button = QPushButton("Prepare MASTER Candidate (Offline)")
    button.setObjectName("prepareVisualIdentityOffline")

    def open_dialog() -> None:
        selected = cap_manager._selected_asset_id()
        if selected is None:
            QMessageBox.information(cap_manager, "Visual Identity", "Select a CAP first.")
            return
        try:
            cap = caps.get(selected)
            coverage = templates.coverage(selected)
            preparation = prepare_visual_identity(
                cap, coverage.template.required_views, coverage.present_views
            )
            if preparation.specification_fingerprint:
                asset = caps.assets.get(selected)
                if preparation.category != asset.category:
                    raise ValueError("Reviewed CAP category differs from the registered asset")
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.warning(cap_manager, "Visual Identity Preparation", str(exc))
            return
        VisualIdentityPreparationDialog(preparation, cap_manager).exec()

    button.clicked.connect(open_dialog)
    outer = cap_manager.layout()
    if outer is None or not outer.count():
        return None
    controls = outer.itemAt(0).layout()
    if controls is None:
        return None
    controls.insertWidget(max(0, controls.count() - 3), button)
    cap_manager.visual_identity_preparation_button = button
    return button
