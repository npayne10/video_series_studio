"""Integrate governed reference-suitability review into Production Planning."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QPushButton, QWidget

from vscs.application.action_performance import ActionPerformanceCompilerService
from vscs.application.asset_compiler import AssetCompilerService
from vscs.application.camera_compiler import CameraCompilerService
from vscs.application.continuity_compiler import ContinuityCompilerService
from vscs.application.governed_reference_suitability_review import (
    GovernedReferenceSuitabilityReviewService,
)
from vscs.application.lighting_compiler import LightingCompilerService
from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService
from vscs.application.style_compiler import StyleCompilerService
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)

from .governed_reference_suitability_review_dialog import (
    GovernedReferenceSuitabilityReviewDialog,
)
from .universal_production_description_compiler_workspace import (
    UniversalProductionDescriptionCompilerWorkspace,
)


class GovernedReferenceSuitabilityWorkspace(UniversalProductionDescriptionCompilerWorkspace):
    """Add explicit reference-suitability authoring before UPD approval."""

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        action_performance: ActionPerformanceCompilerService,
        asset_compiler: AssetCompilerService,
        camera_compiler: CameraCompilerService,
        lighting_compiler: LightingCompilerService,
        continuity_compiler: ContinuityCompilerService,
        style_compiler: StyleCompilerService,
        universal_compiler: UniversalProductionDescriptionCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        self.reference_suitability_authoring = GovernedReferenceSuitabilityReviewService(projects)
        super().__init__(
            projects,
            packages,
            action_performance,
            asset_compiler,
            camera_compiler,
            lighting_compiler,
            continuity_compiler,
            style_compiler,
            universal_compiler,
            parent,
        )
        self._install_reference_suitability_action()
        self._load_universal_draft()

    def _install_reference_suitability_action(self) -> None:
        group = self.universal_create_button.parentWidget()
        if group is None or group.layout() is None:
            raise RuntimeError("Universal Description action layout is unavailable")
        group_layout = group.layout()
        action_item = group_layout.itemAt(group_layout.count() - 1)
        actions = action_item.layout() if action_item is not None else None
        if not isinstance(actions, QHBoxLayout):
            raise RuntimeError("Universal Description action row is unavailable")

        self.reference_suitability_button = QPushButton("Reference Suitability…", group)
        self.reference_suitability_button.setToolTip(
            "Review canonical/composition references explicitly for provider suitability and "
            "persist the governed ReferencePlan. This does not execute a provider."
        )
        insertion = actions.indexOf(self.universal_refresh_button)
        actions.insertWidget(insertion + 1 if insertion >= 0 else 0, self.reference_suitability_button)
        self.reference_suitability_button.clicked.connect(self._open_reference_suitability)

    def _load_universal_draft(self) -> None:
        super()._load_universal_draft()
        if not hasattr(self, "reference_suitability_button"):
            return
        shot_id = self._selected_shot_id
        package = self.packages.current_package(shot_id) if shot_id is not None else None
        self.reference_suitability_button.setEnabled(package is not None)

    def _open_reference_suitability(self) -> None:
        shot_id = self._selected_shot_id
        if shot_id is None:
            return
        package = self.packages.current_package(shot_id)
        if package is None:
            QMessageBox.warning(
                self,
                "Governed Reference Suitability Review",
                "A current Production Package is required before provider suitability can be "
                "reviewed. Refresh the governed Production Planning authorities first.",
            )
            return
        dialog = GovernedReferenceSuitabilityReviewDialog(
            self.reference_suitability_authoring,
            package,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
