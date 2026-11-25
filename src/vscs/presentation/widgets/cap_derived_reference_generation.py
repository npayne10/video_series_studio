"""UI for generating MASTER-conditioned derived CAP production references."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.caps.multiple_angle_execution_guard import stage_offline_qualification
from vscs.application.caps.multiple_angle_live_execution import execute_qualified_multiple_angle
from vscs.application.caps.multiple_angle_runtime_readiness import (
    MultipleAngleRuntimeReadiness,
    plan_multiple_angle_runtime,
)
from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.domain.caps import CanonicalReferenceView, ReferenceRequirement
from vscs.infrastructure.ai.comfyui_derived_reference_provider import (
    ComfyUIDerivedReferenceProvider,
)
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider
from vscs.infrastructure.xcic_core import XCICCoreClient


class GpuQualificationAuthorizationDialog(QDialog):
    """Copyable, exact-match authorization without implicit GPU consent."""

    def __init__(
        self, view: CanonicalReferenceView, phrase: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("One-Use GPU Qualification Authorization")
        self.setMinimumWidth(650)
        self.phrase = phrase
        layout = QVBoxLayout(self)
        explanation = QLabel(
            f"View: {view.value}\n"
            "This stages a new queue and submits exactly one real ComfyUI GPU job. "
            "It can use significant VRAM/time. The resulting image will be a Candidate, "
            "never approved automatically."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        layout.addWidget(QLabel("Copy the exact authorization phrase:"))
        self.phrase_field = QLineEdit(phrase)
        self.phrase_field.setObjectName("gpuQualificationAuthorizationPhrase")
        self.phrase_field.setReadOnly(True)
        self.phrase_field.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        layout.addWidget(self.phrase_field)
        self.copy_button = QPushButton("Copy Authorization Phrase")
        self.copy_button.setObjectName("copyGpuQualificationAuthorization")
        self.copy_button.clicked.connect(self._copy_phrase)
        layout.addWidget(self.copy_button)
        layout.addWidget(QLabel("Paste the phrase below to explicitly authorize this one trial:"))
        self.confirmation_field = QLineEdit()
        self.confirmation_field.setObjectName("gpuQualificationAuthorizationConfirmation")
        layout.addWidget(self.confirmation_field)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.confirm_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm_button.setText("Authorize One GPU Trial")
        self.confirm_button.setEnabled(False)
        self.confirmation_field.textChanged.connect(
            lambda value: self.confirm_button.setEnabled(value == self.phrase)
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _copy_phrase(self) -> None:
        QApplication.clipboard().setText(self.phrase)


class _MultipleAngleQualificationWorker(QThread):
    """One explicitly authorized GPU trial, never an implicit batch run."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: DerivedReferenceGenerationService,
        plan: MultipleAngleRuntimeReadiness,
        model_root: Path,
        authorization: str,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.plan = plan
        self.model_root = model_root
        self.authorization = authorization

    def run(self) -> None:
        try:
            staged = stage_offline_qualification(
                self.service, self.plan, allow_offline_staging=True
            )
            result = execute_qualified_multiple_angle(
                self.service,
                self.plan,
                staged,
                client=XCICCoreClient(os.environ.get("VSCS_COMFYUI_URL", "http://127.0.0.1:8188")),
                model_root=self.model_root,
                authorization=self.authorization,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit((result.reference_record_id,))


class _DerivedGenerationWorker(QThread):
    """Execute provider I/O without blocking Qt's GUI event loop."""

    progress = Signal(str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: DerivedReferenceGenerationService,
        asset_id: str,
        views: tuple[CanonicalReferenceView, ...] | None,
        provider_name: str,
        width: int,
        height: int,
        seed: int,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.asset_id = asset_id
        self.views = views
        self.provider_name = provider_name
        self.width = width
        self.height = height
        self.seed = seed

    def run(self) -> None:
        try:
            if self.views is None:
                created = self.service.generate_missing_required(
                    self.asset_id,
                    provider_name=self.provider_name,
                    width=self.width,
                    height=self.height,
                    seed=self.seed,
                    progress_callback=self.progress.emit,
                )
            else:
                created = self.service.generate(
                    self.asset_id,
                    self.views,
                    provider_name=self.provider_name,
                    width=self.width,
                    height=self.height,
                    seed=self.seed,
                    progress_callback=self.progress.emit,
                )
        except (DerivedReferenceGenerationError, OSError, RuntimeError, ValueError) as exc:
            self.failed.emit(str(exc))
        else:
            self.completed.emit(created)


class DerivedReferenceGenerationDialog(QDialog):
    """Choose category-aware derived views without redefining canonical identity."""

    def __init__(
        self,
        asset_id: str,
        service: DerivedReferenceGenerationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.asset_id = asset_id
        self.service = service
        self._worker: _DerivedGenerationWorker | _MultipleAngleQualificationWorker | None = None
        self._completed_count: int | None = None
        self._last_progress = ""
        self._elapsed = QElapsedTimer()
        self._progress_timer = QTimer(self)
        self._progress_timer.setInterval(1000)
        self._progress_timer.timeout.connect(self._update_elapsed)
        self.coverage = service.coverage(asset_id)
        self.master_ready, master_note = service.master_authority_state(asset_id)
        self.setWindowTitle(f"Generate Production References — {asset_id}")
        self.setMinimumWidth(760)

        intro = QLabel(
            "Reference requirements come from the asset category template. Selected views are "
            "generated from the locked ChatGPT MASTER and enter the CAP as Candidates for review."
        )
        intro.setWordWrap(True)

        self.coverage_label = QLabel(self._coverage_text())
        self.coverage_label.setWordWrap(True)
        self.master_authority_label = QLabel(
            ("MASTER authority verified: " if self.master_ready else "BLOCKED — ") + master_note
        )
        self.master_authority_label.setWordWrap(True)

        self.provider = QComboBox()
        for name in service.providers.names():
            self.provider.addItem(name, name)
        comfy_index = self.provider.findData("ComfyUI — Qwen Derived Reference v2.1")
        if comfy_index >= 0:
            self.provider.setCurrentIndex(comfy_index)

        self.checkboxes: dict[CanonicalReferenceView, QCheckBox] = {}
        grid = QGridLayout()
        views = tuple(
            view
            for view in self.coverage.template.applicable_views
            if view is not CanonicalReferenceView.MASTER
        )
        for index, view in enumerate(views):
            requirement = self.coverage.template.requirement_for(view)
            level = self._requirement_label(requirement)
            present = view in self.coverage.present_views
            state = "Present" if present else "Missing"
            checkbox = QCheckBox(f"{view.value.replace('_', ' ').title()} — {level} ({state})")
            checkbox.setEnabled(not present)
            self.checkboxes[view] = checkbox
            grid.addWidget(checkbox, index // 2, index % 2)

        self.width = QSpinBox()
        self.width.setRange(256, 8192)
        self.width.setValue(1280)
        self.width.setToolTip(
            "Recorded as requested size. Qwen reference workflow currently derives actual geometry "
            "from the MASTER through FluxKontextImageScale."
        )
        self.height = QSpinBox()
        self.height.setRange(256, 8192)
        self.height.setValue(720)
        self.height.setToolTip(self.width.toolTip())
        self.dimension_note = QLabel(
            "Requested dimensions are metadata only for Qwen v2.1. Actual image dimensions "
            "are determined from the MASTER by FluxKontextImageScale."
        )
        self.dimension_note.setWordWrap(True)
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_147_483_647)
        self.seed.setValue(0)

        settings = QGridLayout()
        settings.addWidget(QLabel("Generator"), 0, 0)
        settings.addWidget(self.provider, 0, 1, 1, 3)
        settings.addWidget(QLabel("Width"), 1, 0)
        settings.addWidget(self.width, 1, 1)
        settings.addWidget(QLabel("Height"), 1, 2)
        settings.addWidget(self.height, 1, 3)
        settings.addWidget(QLabel("Seed"), 2, 0)
        settings.addWidget(self.seed, 2, 1)

        self.generate_missing_button = QPushButton("Generate Missing Required Views")
        self.generate_missing_button.setObjectName("generateMissingRequiredViews")
        self.generate_missing_button.clicked.connect(self._generate_missing_required)
        generatable_missing = tuple(
            view
            for view in self.coverage.missing_required
            if view is not CanonicalReferenceView.MASTER
        )
        self.generate_missing_button.setEnabled(self.master_ready and bool(generatable_missing))

        self.qualify_button = QPushButton("Qualify One View (Controlled GPU Trial)")
        self.qualify_button.setObjectName("qualifyMultipleAngleView")
        self.qualify_button.setToolTip(
            "Requires a separate qualification-specific typed GPU authorization. "
            "The generated reference enters Candidate review, never automatic approval."
        )
        self.qualify_button.setEnabled(self.master_ready)
        self.qualify_button.clicked.connect(self._qualify_one_view)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate Selected")
        self.generate_selected_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.generate_selected_button.setEnabled(self.master_ready)
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.master_authority_label)
        layout.addWidget(self.coverage_label)
        layout.addLayout(settings)
        layout.addWidget(self.dimension_note)
        self.progress_label = QLabel("No generation in progress")
        self.progress_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(QLabel("Category production reference views"))
        layout.addLayout(grid)
        layout.addWidget(self.generate_missing_button)
        layout.addWidget(self.qualify_button)
        layout.addWidget(buttons)

    def _qualify_one_view(self) -> None:
        """Plan without side effects before requesting one-use operator consent."""
        if self._worker is not None and self._worker.isRunning():
            return
        views = self.selected_views()
        if len(views) != 1 or views[0] not in {
            CanonicalReferenceView.FRONT,
            CanonicalReferenceView.REAR,
            CanonicalReferenceView.LEFT,
            CanonicalReferenceView.RIGHT,
        }:
            QMessageBox.warning(
                self, "Multiple-Angle Qualification", "Select exactly one missing cardinal view."
            )
            return
        try:
            plan = plan_multiple_angle_runtime(
                self.service, self.asset_id, views[0], seed=self.seed.value()
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "Multiple-Angle Qualification", str(exc))
            return
        root_value, root_confirmed = QInputDialog.getText(
            self,
            "ComfyUI Model Directory",
            "Confirm the installed ComfyUI models directory:",
            text=os.environ.get(
                "VSCS_COMFYUI_MODEL_ROOT",
                r"D:\ComfyUI\ComfyUI_windows_portable\ComfyUI\models",
            ),
        )
        if not root_confirmed or not root_value.strip():
            return
        phrase = f"AUTHORIZE GPU QUALIFICATION {plan.qualification_id}"
        consent = GpuQualificationAuthorizationDialog(views[0], phrase, self)
        if consent.exec() != QDialog.DialogCode.Accepted:
            return
        worker = _MultipleAngleQualificationWorker(
            self.service, plan, Path(root_value), phrase, self
        )
        self._worker = worker
        worker.completed.connect(self._worker_completed)
        worker.failed.connect(self._worker_failed)
        worker.finished.connect(self._worker_finished)
        self._disable_during_generation()
        self._elapsed.start()
        self._progress_timer.start()
        self._show_progress(f"Controlled GPU qualification: {views[0].value}")
        worker.start()

    def _disable_during_generation(self) -> None:
        self.provider.setEnabled(False)
        self.width.setEnabled(False)
        self.height.setEnabled(False)
        self.seed.setEnabled(False)
        self.generate_selected_button.setEnabled(False)
        self.generate_missing_button.setEnabled(False)
        self.qualify_button.setEnabled(False)
        for checkbox in self.checkboxes.values():
            checkbox.setEnabled(False)
        self.progress_bar.setVisible(True)

    def selected_views(self) -> tuple[CanonicalReferenceView, ...]:
        return tuple(view for view, checkbox in self.checkboxes.items() if checkbox.isChecked())

    def _generate(self) -> None:
        views = self.selected_views()
        if not views:
            QMessageBox.warning(self, "Derived References", "Select at least one view to generate.")
            return
        self._run_generation(views)

    def _generate_missing_required(self) -> None:
        self._start_generation(None)

    def _run_generation(self, views: tuple[CanonicalReferenceView, ...]) -> None:
        self._start_generation(views)

    def _start_generation(self, views: tuple[CanonicalReferenceView, ...] | None) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        provider_name = str(self.provider.currentData() or "")
        self._worker = _DerivedGenerationWorker(
            self.service,
            self.asset_id,
            views,
            provider_name,
            self.width.value(),
            self.height.value(),
            self.seed.value(),
            self,
        )
        self._worker.progress.connect(self._show_progress)
        self._worker.completed.connect(self._worker_completed)
        self._worker.failed.connect(self._worker_failed)
        self._worker.finished.connect(self._worker_finished)
        self._disable_during_generation()
        self._elapsed.start()
        self._progress_timer.start()
        self._show_progress(f"Starting {provider_name} — {self._views_text(views or ())}")
        self._worker.start()

    def _show_progress(self, message: str) -> None:
        self._last_progress = message
        self._update_elapsed()

    def _update_elapsed(self) -> None:
        elapsed_seconds = self._elapsed.elapsed() // 1000 if self._elapsed.isValid() else 0
        self.progress_label.setText(f"{self._last_progress}\nElapsed: {elapsed_seconds}s")

    def _worker_completed(self, created: object) -> None:
        self._completed_count = len(created) if isinstance(created, tuple) else 0

    def _worker_failed(self, message: str) -> None:
        self.progress_label.setText(f"Generation failed: {message}")
        QMessageBox.critical(self, "Derived Reference Generation", message)

    def _worker_finished(self) -> None:
        self._progress_timer.stop()
        self.progress_bar.setVisible(False)
        if self._completed_count is not None:
            count = self._completed_count
            self._completed_count = None
            if not count:
                QMessageBox.information(
                    self,
                    "Reference Coverage Complete",
                    "No required derived reference views are missing for this category.",
                )
            else:
                self._generation_complete(count)
            return
        self.provider.setEnabled(True)
        self.width.setEnabled(True)
        self.height.setEnabled(True)
        self.seed.setEnabled(True)
        self.generate_selected_button.setEnabled(self.master_ready)
        self.qualify_button.setEnabled(self.master_ready)
        self.generate_missing_button.setEnabled(
            self.master_ready and bool(self.coverage.missing_required)
        )
        for view, checkbox in self.checkboxes.items():
            checkbox.setEnabled(view not in self.coverage.present_views)

    def reject(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.information(
                self,
                "Generation Running",
                "Generation is still running. Wait for completion before closing this dialog.",
            )
            return
        super().reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._worker is not None and self._worker.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _generation_complete(self, count: int) -> None:
        QMessageBox.information(
            self,
            "Derived References Created",
            f"Created {count} Candidate reference(s). Review and approve them before use.",
        )
        self.accept()

    def _coverage_text(self) -> str:
        category = self.coverage.category.value.replace("_", " ").title()
        missing_required = self._views_text(self.coverage.missing_required)
        missing_recommended = self._views_text(self.coverage.missing_recommended)
        return (
            f"Category: {category}  |  Missing required: {missing_required}  |  "
            f"Missing recommended: {missing_recommended}"
        )

    @staticmethod
    def _views_text(views: tuple[CanonicalReferenceView, ...]) -> str:
        if not views:
            return "None"
        return ", ".join(view.value.replace("_", " ").title() for view in views)

    @staticmethod
    def _requirement_label(requirement: ReferenceRequirement | None) -> str:
        if requirement is None:
            return "Not applicable"
        return requirement.value.title()


def install_derived_reference_generation(cap_manager: QWidget) -> QPushButton | None:
    """Attach the governed derived-reference generator controls to the CAP Manager."""
    references = getattr(cap_manager, "references", None)
    if references is None:
        return None

    registry = DerivedReferenceGeneratorRegistry()
    registry.register(ComfyUIDerivedReferenceProvider())
    registry.register(OfflineDerivedReferencePreviewProvider())
    service = DerivedReferenceGenerationService(
        references,
        ReferenceLibraryService(references),
        registry,
    )
    button = QPushButton("Generate Production References")
    button.setObjectName("generateProductionReferences")
    button.setToolTip("Generate category-aware derived views from the locked ChatGPT MASTER")

    def open_dialog() -> None:
        selected = cap_manager._selected_asset_id()
        if selected is None:
            QMessageBox.information(cap_manager, "Derived References", "Select a CAP first.")
            return
        dialog = DerivedReferenceGenerationDialog(selected, service, cap_manager)
        if dialog.exec():
            cap_manager.refresh()

    button.clicked.connect(open_dialog)
    top_layout = cap_manager.layout()
    if top_layout is None or top_layout.count() == 0:
        return None
    controls = top_layout.itemAt(0).layout()
    if controls is None:
        return None
    controls.insertWidget(max(0, controls.count() - 3), button)
    cap_manager.derived_reference_button = button
    cap_manager.derived_reference_service = service
    return button
