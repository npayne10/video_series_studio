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
from vscs.domain.caps import CanonicalReferenceView
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider


_SELECTABLE_VIEWS = tuple(
    view for view in CanonicalReferenceView if view is not CanonicalReferenceView.MASTER
)


class DerivedReferenceGenerationDialog(QDialog):
    """Choose derived views and generator without redefining canonical identity."""

    def __init__(
        self,
        asset_id: str,
        service: DerivedReferenceGenerationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.asset_id = asset_id
        self.service = service
        self.setWindowTitle(f"Generate Production References — {asset_id}")
        self.setMinimumWidth(680)

        intro = QLabel(
            "Selected views are generated from the locked ChatGPT MASTER. Every output enters "
            "the CAP as a Candidate and must be reviewed before production use."
        )
        intro.setWordWrap(True)

        self.provider = QComboBox()
        for name in service.providers.names():
            self.provider.addItem(name, name)

        self.checkboxes: dict[CanonicalReferenceView, QCheckBox] = {}
        grid = QGridLayout()
        for index, view in enumerate(_SELECTABLE_VIEWS):
            checkbox = QCheckBox(view.value.replace("_", " ").title())
            self.checkboxes[view] = checkbox
            grid.addWidget(checkbox, index // 3, index % 3)

        self.width = QSpinBox()
        self.width.setRange(256, 8192)
        self.width.setValue(1280)
        self.height = QSpinBox()
        self.height.setRange(256, 8192)
        self.height.setValue(720)
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

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate Selected")
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(settings)
        layout.addWidget(QLabel("Production reference views"))
        layout.addLayout(grid)
        layout.addWidget(buttons)

    def selected_views(self) -> tuple[CanonicalReferenceView, ...]:
        return tuple(view for view, checkbox in self.checkboxes.items() if checkbox.isChecked())

    def _generate(self) -> None:
        views = self.selected_views()
        if not views:
            QMessageBox.warning(self, "Derived References", "Select at least one view to generate.")
            return
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
        except (DerivedReferenceGenerationError, OSError, ValueError) as exc:
            QMessageBox.critical(self, "Derived Reference Generation", str(exc))
            return
        QMessageBox.information(
            self,
            "Derived References Created",
            f"Created {len(created)} Candidate reference(s). Review and approve them before use.",
        )
        self.accept()


def install_derived_reference_generation(cap_manager: QWidget) -> QPushButton | None:
    """Attach the 18.2.11.2.5 control to the existing CAP Manager without a UI rewrite."""
    references = getattr(cap_manager, "references", None)
    if references is None:
        return None

    registry = DerivedReferenceGeneratorRegistry()
    registry.register(OfflineDerivedReferencePreviewProvider())
    service = DerivedReferenceGenerationService(
        references,
        ReferenceLibraryService(references),
        registry,
    )
    button = QPushButton("Generate Production References")
    button.setObjectName("generateProductionReferences")
    button.setToolTip("Generate selected derived views from the locked ChatGPT MASTER")

    def open_dialog() -> None:
        selected = getattr(cap_manager, "_selected_asset_id")()
        if selected is None:
            QMessageBox.information(cap_manager, "Derived References", "Select a CAP first.")
            return
        dialog = DerivedReferenceGenerationDialog(selected, service, cap_manager)
        if dialog.exec():
            getattr(cap_manager, "refresh")()

    button.clicked.connect(open_dialog)
    top_layout = cap_manager.layout()
    if top_layout is None or top_layout.count() == 0:
        return None
    controls = top_layout.itemAt(0).layout()
    if controls is None:
        return None
    controls.insertWidget(max(0, controls.count() - 3), button)
    setattr(cap_manager, "derived_reference_button", button)
    setattr(cap_manager, "derived_reference_service", service)
    return button
