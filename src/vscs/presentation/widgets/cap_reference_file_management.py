"""UI integration for managed canonical references, approvals, and generation."""

from __future__ import annotations

import getpass
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.asset_generator import (
    CanonicalAssetGenerationError,
    CanonicalAssetGeneratorService,
)
from vscs.application.caps.file_manager import (
    CanonicalReferenceFileError,
    CanonicalReferenceFileManager,
    DuplicateFileResolution,
)
from vscs.application.caps.readiness_service import CAPReadinessService
from vscs.application.caps.reference_library import (
    ReferenceLibraryError,
    ReferenceLibraryNotFoundError,
    ReferenceLibraryService,
)
from vscs.application.caps.reference_service import (
    CanonicalReferenceError,
    CanonicalReferenceService,
)
from vscs.domain.caps import (
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceView,
)
from vscs.domain.caps.reference_library import ReferenceLibraryEntry
from vscs.infrastructure.xcic import XCICImageProvider
from vscs.presentation.dialogs.canonical_asset_generation_dialog import (
    CanonicalAssetGenerationDialog,
)
from vscs.presentation.widgets import cap_manager
from vscs.presentation.widgets.canonical_reference_gallery import CanonicalReferenceGallery


class ReferenceEvidenceDialog(QDialog):
    """Resizable review form with readable instructions and an editable evidence note."""

    def __init__(
        self,
        title: str,
        instructions: str,
        parent: QWidget | None = None,
        *,
        prepared_context: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(440, 250)
        self.resize(780, 370)
        layout = QVBoxLayout(self)
        self.instruction_label = QLabel(instructions)
        self.instruction_label.setObjectName("referenceEvidenceInstructions")
        self.instruction_label.setWordWrap(True)
        layout.addWidget(self.instruction_label)
        if prepared_context:
            self.context_label = QLabel(
                "Prepared record context (not approval evidence):\n" + prepared_context
            )
            self.context_label.setObjectName("referenceEvidencePreparedContext")
            self.context_label.setWordWrap(True)
            self.context_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(self.context_label)
        self.evidence_edit = QPlainTextEdit()
        self.evidence_edit.setObjectName("referenceEvidenceNote")
        self.evidence_edit.setPlaceholderText("Record the observed evidence and any limitations…")
        layout.addWidget(self.evidence_edit, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


def _request_reference_evidence(
    dialog: Any, title: str, instructions: str, *, prepared_context: str = ""
) -> tuple[str, bool]:
    review = ReferenceEvidenceDialog(
        title, instructions, parent=dialog, prepared_context=prepared_context
    )
    if review.exec() != QDialog.DialogCode.Accepted:
        return "", False
    return review.evidence_edit.toPlainText().strip(), True


def _prepared_reference_context(reference: Any, registered: ReferenceLibraryEntry) -> str:
    """Expose persisted identifiers and source lineage; never fabricate QC findings."""
    details = [
        f"Asset: {registered.asset_id}",
        f"Requested view: {registered.view.value}",
        f"Reference: {registered.reference_id} (record {registered.reference_record_id})",
        f"Candidate file: {reference.file_path}",
        f"Lifecycle: {registered.lifecycle.value}",
    ]
    if registered.source_master_version:
        details.append(f"Source MASTER version: {registered.source_master_version}")
    details.append("Camera alignment and unseen geometry: not independently verified by VSCS.")
    return "\n".join(details)


class CinematicCrossViewDialog(QDialog):
    """Compare actual managed images, then collect a separate human-use judgment."""

    def __init__(
        self,
        references: CanonicalReferenceService,
        entries: tuple[ReferenceLibraryEntry, ...],
        root: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cross-View Cinematic Acceptance — Human QC")
        self.resize(1020, 600)
        layout = QVBoxLayout(self)
        guidance = QLabel(
            "Compare the locked MASTER, approved Front and available side/rear candidates. "
            "Accept only if overall silhouette, materials, identity and continuity are "
            "suitable for cinematic video. This does NOT verify unseen geometry or "
            "approve a canonical reference."
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        project = root.resolve(strict=False)
        for entry in entries:
            column = QVBoxLayout()
            path = (project / references.get(entry.reference_record_id).file_path).resolve(
                strict=False
            )
            caption = QLabel(f"{entry.view.value.title()} — {entry.lifecycle.value.title()}")
            caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(caption)
            picture = QLabel()
            picture.setObjectName(f"cinematicComparisonImage_{entry.reference_record_id}")
            picture.setFixedSize(180, 210)
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if path.is_relative_to(project) and path.is_file():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    picture.setPixmap(
                        pixmap.scaled(
                            picture.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            column.addWidget(picture)
            cell = QWidget()
            cell.setLayout(column)
            strip_layout.addWidget(cell)
        strip_layout.addStretch()
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        scroller.setWidget(strip)
        layout.addWidget(scroller, 1)
        self.assessment = QPlainTextEdit()
        self.assessment.setObjectName("cinematicAssessment")
        self.assessment.setPlaceholderText(
            "Describe cross-view identity and continuity, camera-angle limitations "
            "and any visible contradictions (at least 30 characters)."
        )
        layout.addWidget(self.assessment)
        self.confirm = QCheckBox(
            "I independently reviewed the displayed views and accept this candidate "
            "for cinematic use only; no unseen geometry is declared canonical."
        )
        self.confirm.setObjectName("cinematicAcceptanceConfirmation")
        layout.addWidget(self.confirm)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Accept Cinematic Use")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        if not self.confirm.isChecked() or len(self.assessment.toPlainText().strip()) < 30:
            QMessageBox.warning(
                self,
                "Human Cinematic QC Required",
                "Review the views, provide substantive QC observations and check "
                "the independent cinematic-use confirmation.",
            )
            return
        self.accept()


class CanonicalReferenceDropFilter(QObject):
    """Accept local files dropped onto the Canonical References gallery."""

    def __init__(self, dialog: Any) -> None:
        super().__init__(dialog)
        self.dialog = dialog

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.DragEnter:
            mime = event.mimeData()  # type: ignore[attr-defined]
            if mime.hasUrls() and any(url.isLocalFile() for url in mime.urls()):
                event.acceptProposedAction()  # type: ignore[attr-defined]
                return True
        if event.type() == QEvent.Type.Drop:
            mime = event.mimeData()  # type: ignore[attr-defined]
            files = [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]
            if files:
                _import_sources(self.dialog, files)
                event.acceptProposedAction()  # type: ignore[attr-defined]
                return True
        return super().eventFilter(watched, event)


def _duplicate_resolution(parent: Any, destination: Path) -> DuplicateFileResolution:
    box = QMessageBox(parent)
    box.setWindowTitle("Canonical Reference Already Exists")
    box.setText(f"A managed reference named {destination.name} already exists.")
    box.setInformativeText("Choose whether to replace it, keep both files, or cancel the import.")
    replace = box.addButton("Replace", QMessageBox.ButtonRole.DestructiveRole)
    keep_both = box.addButton("Keep Both", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(keep_both)
    box.exec()
    if box.clickedButton() is replace:
        return DuplicateFileResolution.REPLACE
    if box.clickedButton() is keep_both:
        return DuplicateFileResolution.KEEP_BOTH
    if box.clickedButton() is cancel:
        return DuplicateFileResolution.CANCEL
    return DuplicateFileResolution.CANCEL


def _import_sources(dialog: Any, sources: list[Path]) -> None:
    if (
        dialog.profile is None
        or dialog.reference_service is None
        or dialog.project_directory is None
    ):
        return
    manager = CanonicalReferenceFileManager(dialog.project_directory)
    for source in sources:
        if not source.is_file():
            continue
        reference_type = manager.detect_type(source)
        destination = manager.destination_for(dialog.profile.asset_id, source, reference_type)
        resolution = DuplicateFileResolution.KEEP_BOTH
        if destination.exists() and source.resolve(strict=False) != destination.resolve(
            strict=False
        ):
            resolution = _duplicate_resolution(dialog, destination)
            if resolution is DuplicateFileResolution.CANCEL:
                continue
        try:
            managed = manager.import_file(
                dialog.profile.asset_id,
                source,
                reference_type=reference_type,
                duplicate_resolution=resolution,
            )
            editor = cap_manager.CanonicalReferenceEditorDialog(
                dialog.project_directory, parent=dialog
            )
            editor.title.setText(source.stem.replace("_", " ").replace("-", " ").title())
            editor.file_path.setText(str(managed.relative_path))
            editor.reference_type.setCurrentIndex(
                editor.reference_type.findData(managed.reference_type)
            )
            editor.role.setCurrentIndex(editor.role.findData(CanonicalReferenceRole.SUPPLEMENTARY))
            editor.status.setCurrentIndex(editor.status.findData(CanonicalReferenceStatus.IMPORTED))
            editor.status.setEnabled(False)
            editor.notes.setPlainText(
                "Managed by VSCS\n"
                f"SHA256: {managed.sha256}\n"
                f"Size: {managed.size_bytes} bytes\n"
                f"Modified: {managed.modified_at}"
            )
            if not editor.exec():
                continue
            dialog.reference_service.create(
                dialog.profile.asset_id,
                editor.create_value(dialog.profile.id),
            )
        except (CanonicalReferenceFileError, CanonicalReferenceError, ValueError, OSError) as exc:
            QMessageBox.critical(dialog, "Canonical Reference Import Error", str(exc))
    dialog._refresh_references()


def _managed_add_reference(dialog: Any) -> None:
    if (
        dialog.profile is None
        or dialog.reference_service is None
        or dialog.project_directory is None
    ):
        return
    files, _ = QFileDialog.getOpenFileNames(
        dialog,
        "Import Canonical References",
        str(Path.home()),
        "All Files (*)",
    )
    if files:
        _import_sources(dialog, [Path(filename) for filename in files])


def _generate_references(dialog: Any) -> None:
    if (
        dialog.profile is None
        or dialog.reference_service is None
        or dialog.project_directory is None
    ):
        return
    default_prompt = "\n\n".join(
        value
        for value in (
            dialog.description.toPlainText().strip(),
            dialog.visual_identity.toPlainText().strip(),
        )
        if value
    )
    editor = CanonicalAssetGenerationDialog(default_prompt, dialog)
    if not editor.exec():
        return
    try:
        generator = CanonicalAssetGeneratorService(
            dialog.reference_service,
            XCICImageProvider(dialog.project_directory),
        )
        created = generator.generate(dialog.profile.asset_id, editor.request_value())
    except (CanonicalAssetGenerationError, CanonicalReferenceError, ValueError, OSError) as exc:
        QMessageBox.critical(dialog, "Canonical Asset Generation", str(exc))
        return
    dialog._refresh_references()
    QMessageBox.information(
        dialog,
        "Canonical Asset Generation",
        f"Generated {len(created)} versioned Candidate reference(s) using the "
        "XCIC Rendering Engine and ComfyUI.\n\n"
        "The generated PNG files were imported into the Canonical Reference Gallery. "
        "Prompt, model, seed, dimensions, provider, and generation time were stored in "
        "provenance manifests.",
    )


def _run_workflow(dialog: Any, action: Callable[[], object], success: str | None = None) -> None:
    try:
        action()
    except (CanonicalReferenceError, ReferenceLibraryError, ValueError) as exc:
        QMessageBox.critical(dialog, "Canonical Reference Workflow", str(exc))
        return
    if success:
        dialog.statusTip = success
    dialog._refresh_references()


def _registered_reference(
    dialog: Any, reference_id: int
) -> tuple[ReferenceLibraryService, ReferenceLibraryEntry | None]:
    """Never mistake a gallery-only reference for a governed production reference."""
    library = ReferenceLibraryService(dialog.reference_service)
    try:
        return library, library.get(reference_id)
    except ReferenceLibraryNotFoundError:
        return library, None


def _set_primary_reference(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None:

        def apply() -> object:
            _library, registered = _registered_reference(dialog, reference_id)
            if registered is not None:
                raise CanonicalReferenceError(
                    "Governed MASTER and derived reference roles cannot be changed in the "
                    "gallery. MASTER authority is managed from Assets; derived views stay "
                    "Supplementary."
                )
            asset_id = getattr(getattr(dialog, "profile", None), "asset_id", None)
            if isinstance(asset_id, str) and any(
                entry.family is CanonicalReferenceFamily.MASTER
                and entry.lifecycle is not CanonicalReferenceLifecycle.ARCHIVED
                for entry in _library.list_for_cap(asset_id)
            ):
                raise CanonicalReferenceError(
                    "This CAP already has a governed MASTER. Gallery Primary cannot replace "
                    "or compete with its authority; use Assets for an approved MASTER revision."
                )
            if (
                QMessageBox.question(
                    dialog,
                    "Gallery Primary Role Only",
                    "Set this unregistered reference as the gallery Primary? This does NOT "
                    "create or approve a ChatGPT MASTER and does NOT satisfy governed "
                    "reference readiness.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                is not QMessageBox.StandardButton.Yes
            ):
                return None
            return dialog.reference_service.set_primary(reference_id)

        _run_workflow(dialog, apply)


def _mark_candidate(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is not None:

        def apply() -> object:
            library, registered = _registered_reference(dialog, reference_id)
            if registered is not None:
                return library.mark_candidate(reference_id, actor=getpass.getuser())
            return dialog.reference_service.mark_candidate(reference_id)

        _run_workflow(dialog, apply)


def _approve(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is None:
        return
    reference = dialog.reference_service.get(reference_id)
    try:
        _library, registered = _registered_reference(dialog, reference_id)
    except ReferenceLibraryError as exc:
        QMessageBox.critical(dialog, "Canonical Reference Workflow", str(exc))
        return
    if registered is not None and registered.family is CanonicalReferenceFamily.MASTER:
        QMessageBox.critical(
            dialog,
            "MASTER Governance",
            "MASTER approval and locking are owned by Assets. Do not promote or "
            "reclassify a MASTER through the Canonical Profile gallery.",
        )
        return
    review_note = ""
    if (
        registered is not None
        and registered.view
        in {
            CanonicalReferenceView.FRONT,
            CanonicalReferenceView.REAR,
            CanonicalReferenceView.LEFT,
            CanonicalReferenceView.RIGHT,
        }
        and "_qualification_" in Path(reference.file_path).name
    ):
        viewpoint, accepted = _request_reference_evidence(
            dialog,
            "Viewpoint Acceptance — Independent QC",
            "Confirm this is the requested cardinal elevation. Record alignment evidence "
            "including any visible side/top face, yaw/elevation error and whether the "
            "viewpoint passes. Cancel if the camera is not acceptable.",
            prepared_context=_prepared_reference_context(reference, registered),
        )
        if not accepted or len(viewpoint.strip()) < 30:
            QMessageBox.warning(
                dialog, "Viewpoint Review Required", "Viewpoint acceptance is required."
            )
            return
        camera_response = QMessageBox.question(
            dialog,
            "Accept Camera Viewpoint?",
            "Does the image PASS the requested cardinal viewpoint, including "
            "camera alignment and acceptable side/top visibility?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if camera_response != QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                dialog,
                "Approval Not Completed — Camera Viewpoint",
                "The camera viewpoint was not confirmed as passing. The reference "
                "remains a Candidate; no approval was recorded.",
            )
            return
        review_note = f"VIEWPOINT ACCEPTANCE: PASS — {viewpoint.strip()}"
    if (
        registered is not None
        and registered.view
        in {
            CanonicalReferenceView.REAR,
            CanonicalReferenceView.LEFT,
            CanonicalReferenceView.RIGHT,
        }
        and "_qualification_" in Path(reference.file_path).name
    ):
        attestation, accepted = _request_reference_evidence(
            dialog,
            "Canonical Geometry Evidence Required",
            "Independent geometry acceptance: identify the approved source drawings, "
            "multi-view references or other operator-verified design evidence. "
            "Explain how newly visible panels, vents and structural features were checked. "
            "The front-only MASTER does not establish unseen rear/side features. "
            "If no such evidence exists, "
            "Cancel and keep the image Candidate or reject it. Do not infer canon "
            "from model plausibility.",
            prepared_context=_prepared_reference_context(reference, registered),
        )
        if not accepted or len(attestation.strip()) < 30:
            QMessageBox.warning(
                dialog,
                "Geometry Review Required",
                "Approval requires a substantive human canonical geometry review.",
            )
            return
        geometry_response = QMessageBox.question(
            dialog,
            "Verify Canonical Geometry?",
            "Have ALL newly visible structural features been verified against "
            "independent design authority? If any are unknown, select No and "
            "retain the Candidate.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if geometry_response != QMessageBox.StandardButton.Yes:
            QMessageBox.information(
                dialog,
                "Approval Not Completed — Canonical Geometry",
                "Independent geometry verification was not confirmed. The reference "
                "remains a Candidate; no approval was recorded.",
            )
            return
        review_note += f"\nCANONICAL GEOMETRY REVIEW: VERIFIED — {attestation.strip()}"
    authority_note = (
        "The old gallery already marked this reference Approved, but its governed "
        "library entry is still Candidate. Confirm this separate governed approval."
        if registered is not None
        and registered.lifecycle is CanonicalReferenceLifecycle.CANDIDATE
        and reference.status is CanonicalReferenceStatus.APPROVED
        else (
            "The governed library will record this view's independent approval."
            if registered is not None
            else "This unregistered gallery reference does NOT establish MASTER or satisfy "
            "governed production-view readiness."
        )
    )
    final_response = QMessageBox.question(
        dialog,
        "Approve Canonical Reference",
        f"Approve '{reference.title}'?\n\nThe reference will become locked.\n\n{authority_note}",
    )
    if final_response != QMessageBox.StandardButton.Yes:
        QMessageBox.information(
            dialog,
            "Approval Not Completed — Final Confirmation",
            "Final approval was not confirmed. The reference remains a Candidate; "
            "no approval was recorded.",
        )
        return

    def apply() -> object:
        library, entry = _registered_reference(dialog, reference_id)
        if entry is not None:
            return library.approve(reference_id, getpass.getuser(), note=review_note)
        return dialog.reference_service.approve(reference_id, getpass.getuser())

    _run_workflow(dialog, apply)


def _accept_cinematic(dialog: Any, reference_id: int) -> None:
    """Record a limited-use decision without invoking canonical approval."""
    if dialog.reference_service is None or dialog.project_directory is None:
        return
    library = ReferenceLibraryService(dialog.reference_service)
    try:
        entry = library.get(reference_id)
        comparisons = library.cinematic_comparison(reference_id)
        if entry.lifecycle is not CanonicalReferenceLifecycle.CANDIDATE:
            raise ReferenceLibraryError("Only Candidate references may be accepted for cinema")
    except ReferenceLibraryError as exc:
        QMessageBox.warning(dialog, "Cinematic Review Unavailable", str(exc))
        return
    review = CinematicCrossViewDialog(
        dialog.reference_service, comparisons, dialog.project_directory, parent=dialog
    )
    if review.exec() != QDialog.DialogCode.Accepted:
        return
    if (
        QMessageBox.question(
            dialog,
            "Confirm Cinematic-Only Acceptance?",
            "Record limited cinematic-use acceptance for this Candidate? "
            "It will NOT become an Approved or Locked canonical reference.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        != QMessageBox.StandardButton.Yes
    ):
        return

    def apply() -> object:
        return library.accept_cinematic(
            reference_id, getpass.getuser(), review.assessment.toPlainText()
        )

    _run_workflow(dialog, apply)


def _show_cinematic_readiness(dialog: Any) -> None:
    if dialog.reference_service is None or dialog.profile is None:
        return
    try:
        report = CAPReadinessService(
            dialog.reference_service.caps, dialog.reference_service
        ).evaluate_cinematic(dialog.profile.asset_id)
    except (ReferenceLibraryError, CanonicalReferenceError, ValueError) as exc:
        QMessageBox.warning(dialog, "Cinematic Readiness Unavailable", str(exc))
        return
    gaps = "\n".join(f"• {gap.message}" for gap in report.blocking_gaps) or "No blockers"
    QMessageBox.information(
        dialog,
        "Cinematic Production Readiness — Separate Assessment",
        f"Cinematic overall: {report.overall_score}%\n"
        f"Cinematic reference readiness: {report.references.score}%\n"
        f"Generation gate: {report.generation.state.value}\n\n"
        f"Remaining blockers:\n{gaps}\n\n"
        "Canonical readiness and approval remain unchanged. No GPU job was submitted.",
    )


def _reject(dialog: Any, reference_id: int) -> None:
    if dialog.reference_service is None:
        return
    try:
        _library, registered = _registered_reference(dialog, reference_id)
    except ReferenceLibraryError as exc:
        QMessageBox.critical(dialog, "Canonical Reference Workflow", str(exc))
        return
    if registered is not None and registered.family is CanonicalReferenceFamily.MASTER:
        QMessageBox.critical(
            dialog, "MASTER Governance", "The locked MASTER cannot be rejected here."
        )
        return
    if registered is not None and registered.lifecycle is CanonicalReferenceLifecycle.CANDIDATE:
        reason, accepted = QInputDialog.getMultiLineText(
            dialog,
            "Reject Derived Candidate — Quality Control",
            "Document the observed failure and requested correction. The image and review "
            "history will be retained:",
        )
        if not accepted:
            return
        reason = reason.strip()
        if not reason:
            QMessageBox.warning(dialog, "QC reason required", "Enter a QC rejection reason.")
            return
        if (
            QMessageBox.question(
                dialog,
                "Confirm Candidate Rejection",
                "Reject this derived Candidate with the recorded reason? "
                "Its image will be retained; a replacement may then be generated.",
            )
            is not QMessageBox.StandardButton.Yes
        ):
            return

        def reject_candidate() -> object:
            library, _entry = _registered_reference(dialog, reference_id)
            return library.reject(reference_id, actor=getpass.getuser(), note=reason)

        _run_workflow(dialog, reject_candidate)
        return
    if (
        QMessageBox.question(
            dialog,
            "Return to Candidate",
            "Remove production approval and return this reference to Candidate status?",
        )
        is QMessageBox.StandardButton.Yes
    ):

        def apply() -> object:
            library, registered = _registered_reference(dialog, reference_id)
            if registered is not None:
                return library.return_to_candidate(reference_id, actor=getpass.getuser())
            return dialog.reference_service.reject(reference_id)

        _run_workflow(dialog, apply)


def _archive(dialog: Any, reference_id: int) -> None:
    if (
        dialog.reference_service is not None
        and QMessageBox.question(
            dialog,
            "Archive Canonical Reference",
            "Archive this reference? Archived references remain in the project but cannot be edited or used for production.",
        )
        is QMessageBox.StandardButton.Yes
    ):

        def apply() -> object:
            library, registered = _registered_reference(dialog, reference_id)
            if registered is not None:
                if registered.family is CanonicalReferenceFamily.MASTER:
                    raise CanonicalReferenceError(
                        "A governed MASTER can only be archived as part of a reviewed "
                        "revision in Assets, after dependent derived views are resolved."
                    )
                return library.archive(reference_id, actor=getpass.getuser())
            return dialog.reference_service.archive(reference_id)

        _run_workflow(dialog, apply)


def _unlock(dialog: Any, reference_id: int) -> None:
    if (
        dialog.reference_service is not None
        and QMessageBox.question(
            dialog,
            "Unlock Canonical Reference",
            "Unlocking removes production approval and returns the reference to Candidate status. Continue?",
        )
        is QMessageBox.StandardButton.Yes
    ):

        def apply() -> object:
            library, registered = _registered_reference(dialog, reference_id)
            if registered is not None:
                return library.return_to_candidate(reference_id, actor=getpass.getuser())
            return dialog.reference_service.unlock(reference_id)

        _run_workflow(dialog, apply)


def _update_edit_controls(dialog: Any) -> None:
    gallery = getattr(dialog, "reference_gallery", None)
    reference = None if gallery is None else gallery.selected_reference()
    enabled = reference is not None and not reference.locked
    dialog.edit_reference_button.setEnabled(enabled)
    dialog.remove_reference_button.setEnabled(enabled)


def install_canonical_reference_file_management() -> None:
    """Extend the CAP editor with managed imports, generation, gallery, and approvals."""
    if getattr(cap_manager.CAPEditorDialog, "_managed_reference_files_installed", False):
        return

    original_init = cap_manager.CAPEditorDialog.__init__
    original_refresh = cap_manager.CAPEditorDialog._refresh_references
    original_selected_reference_id = cap_manager.CAPEditorDialog._selected_reference_id

    def managed_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.reference_gallery = CanonicalReferenceGallery(self)
        self.reference_gallery.reference_activated.connect(lambda _id: self._edit_reference())
        self.reference_gallery.primary_requested.connect(
            lambda rid: _set_primary_reference(self, rid)
        )
        self.reference_gallery.candidate_requested.connect(lambda rid: _mark_candidate(self, rid))
        self.reference_gallery.approve_requested.connect(lambda rid: _approve(self, rid))
        self.reference_gallery.cinematic_requested.connect(lambda rid: _accept_cinematic(self, rid))
        self.reference_gallery.cinematic_readiness_requested.connect(
            lambda: _show_cinematic_readiness(self)
        )
        self.reference_gallery.reject_requested.connect(lambda rid: _reject(self, rid))
        self.reference_gallery.archive_requested.connect(lambda rid: _archive(self, rid))
        self.reference_gallery.unlock_requested.connect(lambda rid: _unlock(self, rid))
        self.reference_gallery.gallery.currentItemChanged.connect(
            lambda *_: _update_edit_controls(self)
        )

        self.generate_reference_button = QPushButton("Generate Canonical Images…")
        self.generate_reference_button.setObjectName("generateCanonicalImagesButton")
        self.generate_reference_button.setEnabled(
            self.profile is not None and self.reference_service is not None
        )
        self.generate_reference_button.clicked.connect(lambda: _generate_references(self))

        self.references.hide()
        self.layout().insertWidget(1, self.reference_gallery, 1)
        self.layout().insertWidget(2, self.generate_reference_button)
        self.reference_gallery.setAcceptDrops(True)
        self._canonical_reference_drop_filter = CanonicalReferenceDropFilter(self)
        self.reference_gallery.installEventFilter(self._canonical_reference_drop_filter)
        self.reference_gallery.gallery.installEventFilter(self._canonical_reference_drop_filter)
        self.reference_gallery.setToolTip(
            "Drop files here to copy them into managed Canonical Assets storage."
        )
        if self.profile is not None and self.project_directory is not None:
            CanonicalReferenceFileManager(self.project_directory).ensure_asset_structure(
                self.profile.asset_id
            )
        self._refresh_references()

    def managed_refresh(self: Any) -> None:
        original_refresh(self)
        gallery = getattr(self, "reference_gallery", None)
        if gallery is None:
            return
        if self.profile is None or self.reference_service is None:
            gallery.set_references((), self.project_directory)
            return
        try:
            references = self.reference_service.list_for_cap(self.profile.asset_id)
            governed = ReferenceLibraryService(self.reference_service).list_for_cap(
                self.profile.asset_id, include_archived=True
            )
        except (CanonicalReferenceError, ReferenceLibraryError) as exc:
            QMessageBox.critical(self, "Canonical Reference Error", str(exc))
            return
        gallery.set_references(references, self.project_directory, governed_entries=governed)
        _update_edit_controls(self)

    def managed_selected_reference_id(self: Any) -> int | None:
        gallery = getattr(self, "reference_gallery", None)
        if gallery is not None:
            reference_id = gallery.selected_reference_id()
            if reference_id is not None:
                return reference_id
        return original_selected_reference_id(self)

    cap_manager.CAPEditorDialog.__init__ = managed_init
    cap_manager.CAPEditorDialog._refresh_references = managed_refresh
    cap_manager.CAPEditorDialog._selected_reference_id = managed_selected_reference_id
    cap_manager.CAPEditorDialog._add_reference = _managed_add_reference
    cap_manager.CAPEditorDialog._managed_reference_files_installed = True
