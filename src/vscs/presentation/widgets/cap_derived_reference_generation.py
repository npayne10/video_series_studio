"""UI for generating MASTER-conditioned derived CAP production references."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QMessageBox,
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
from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.domain.caps import CanonicalReferenceView, ReferenceRequirement
from vscs.infrastructure.ai.comfyui_derived_reference_provider import (
    ComfyUIDerivedReferenceProvider,
)
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider


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
        self.coverage = service.coverage(asset_id)
        self.setWindowTitle(f"Generate Production References — {asset_id}")
        self.setMinimumWidth(760)

        intro = QLabel(
            "Reference requirements come from the asset category template. Selected views are "
            "generated from the locked ChatGPT MASTER and enter the CAP as Candidates for review."
        )
        intro.setWordWrap(True)

        self.coverage_label = QLabel(self._coverage_text())
        self.coverage_label.setWordWrap(True)

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
        self.generate_missing_button.setEnabled(bool(generatable_missing))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate Selected")
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.coverage_label)
        layout.addLayout(settings)
        layout.addWidget(QLabel("Category production reference views"))
        layout.addLayout(grid)
        layout.addWidget(self.generate_missing_button)
        layout.addWidget(buttons)

    def selected_views(self) -> tuple[CanonicalReferenceView, ...]:
        return tuple(view for view, checkbox in self.checkboxes.items() if checkbox.isChecked())

    def _generate(self) -> None:
        views = self.selected_views()
        if not views:
            QMessageBox.warning(self, "Derived References", "Select at least one view to generate.")
            return
        self._run_generation(views)

    def _generate_missing_required(self) -> None:
        provider_name = str(self.provider.currentData() or "")
        try:
            created = self.service.generate_missing_required(
                self.asset_id,
                provider_name=provider_name,
                width=self.width.value(),
                height=self.height.value(),
                seed=self.seed.value(),
            )
        except (DerivedReferenceGenerationError, OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "Derived Reference Generation", str(exc))
            return
        if not created:
            QMessageBox.information(
                self,
                "Reference Coverage Complete",
                "No required derived reference views are missing for this category.",
            )
            return
        self._generation_complete(len(created))

    def _run_generation(self, views: tuple[CanonicalReferenceView, ...]) -> None:
        provider_name = str(self.provider.currentData() or "")
        try:
            created = self.service.generate(
                self.asset_id,
                views,
                provider_name=provider_name,
                width=self.width.value(),
                height=self.height.value(),
                seed=self.seed.value(),
            )
        except (DerivedReferenceGenerationError, OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(self, "Derived Reference Generation", str(exc))
            return
        self._generation_complete(len(created))

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
