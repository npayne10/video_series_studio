"""Authoritative Shot Asset Resolver UI for Phase 19.3.4."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionStatus,
)
from vscs.application.story import (
    AssetBindingStatus,
    GovernedAssetResolutionError,
    GovernedAssetResolutionService,
    ShotAssetBinding,
    ShotPlan,
)
from vscs.domain.assets import AssetCategory


EXCLUDED_CATEGORIES = {
    AssetCategory.CAMERA,
    AssetCategory.LIGHTING,
    AssetCategory.REFERENCE,
}


@dataclass(frozen=True, slots=True)
class AssetBindingEditorValues:
    """Normalized values returned by the governed asset-binding editor."""

    sequence_number: int
    role: str
    requirement: str
    expected_category: AssetCategory
    asset_id: str
    notes: str


class AssetBindingEditorDialog(QDialog):
    """Edit only information owned by Phase 19.3.4 asset resolution."""

    def __init__(
        self,
        service: GovernedAssetResolutionService,
        shot: ShotPlan,
        binding: ShotAssetBinding | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.shot = shot
        self.setObjectName("assetBindingEditorDialog")
        self.setWindowTitle("Edit Asset Binding" if binding else "New Asset Requirement")
        self.setMinimumSize(640, 430)

        self.sequence_spin = QSpinBox(self)
        self.sequence_spin.setRange(1, 9999)
        self.sequence_spin.setValue(binding.sequence_number if binding else 1)
        self.sequence_spin.setEnabled(binding is None)
        self.role_edit = QLineEdit(binding.role if binding else "", self)
        self.requirement_edit = QPlainTextEdit(binding.requirement if binding else "", self)
        self.category_combo = QComboBox(self)
        for category in AssetCategory:
            if category not in EXCLUDED_CATEGORIES:
                self.category_combo.addItem(category.value.title(), category)
        if binding is not None:
            index = self.category_combo.findData(binding.expected_category)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)
        self.asset_combo = QComboBox(self)
        self.asset_combo.setObjectName("governedAssetSelection")
        self.notes_edit = QPlainTextEdit(binding.notes if binding else "", self)
        self.readiness_label = QLabel(self)
        self.readiness_label.setObjectName("assetBindingReadiness")
        self.readiness_label.setWordWrap(True)

        guidance = QLabel(
            "Bind this Shot requirement to an existing project asset. Camera and lighting profiles are "
            "owned by later specialist planners. Production approval requires an approved Asset, CAP and "
            "approved canonical reference.",
            self,
        )
        guidance.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Sequence", self.sequence_spin)
        form.addRow("Production role *", self.role_edit)
        form.addRow("Requirement *", self.requirement_edit)
        form.addRow("Asset category *", self.category_combo)
        form.addRow("Project asset", self.asset_combo)
        form.addRow("Notes", self.notes_edit)
        form.addRow("Current resolution", self.readiness_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(guidance)
        root.addLayout(form)
        root.addStretch(1)
        root.addWidget(buttons)

        self.category_combo.currentIndexChanged.connect(lambda _index: self._reload_assets())
        self.asset_combo.currentIndexChanged.connect(self._refresh_readiness)
        self._reload_assets(binding.asset_id if binding else "")

    def _reload_assets(self, selected_asset_id: str = "") -> None:
        category = self.category_combo.currentData()
        if not isinstance(category, AssetCategory):
            return
        current_asset = selected_asset_id or str(self.asset_combo.currentData() or "")
        self.asset_combo.blockSignals(True)
        self.asset_combo.clear()
        self.asset_combo.addItem("— Unbound —", "")
        try:
            choices = self.service.available_assets(category)
        except GovernedAssetResolutionError:
            choices = ()
        for asset_id, name in choices:
            self.asset_combo.addItem(f"{asset_id} — {name}", asset_id)
        index = self.asset_combo.findData(current_asset)
        self.asset_combo.setCurrentIndex(index if index >= 0 else 0)
        self.asset_combo.blockSignals(False)
        self._refresh_readiness()

    def _refresh_readiness(self) -> None:
        asset_id = str(self.asset_combo.currentData() or "")
        category = self.category_combo.currentData()
        if not asset_id or not isinstance(category, AssetCategory):
            self.readiness_label.setText("Unbound — requirement may be saved as Draft.")
            return
        result = self.service.resolver.resolve(
            AssetResolutionRequest(
                asset_id,
                expected_category=category,
                require_approved_asset=True,
                require_cap=True,
                require_approved_cap=True,
                require_approved_references=True,
            )
        )
        if result.status is AssetResolutionStatus.RESOLVED:
            reference_count = len(result.references)
            cap_version = result.cap.version if result.cap is not None else "—"
            self.readiness_label.setText(
                f"Resolved — approved CAP {cap_version}; {reference_count} approved canonical reference(s)."
            )
            return
        diagnostics = "; ".join(item.message for item in result.diagnostics) or result.status.value
        self.readiness_label.setText(f"{result.status.value.title()} — {diagnostics}")

    def _accept_if_valid(self) -> None:
        if not self.role_edit.text().strip():
            QMessageBox.warning(self, "Asset Resolver", "Production role is required.")
            return
        if not self.requirement_edit.toPlainText().strip():
            QMessageBox.warning(self, "Asset Resolver", "Asset requirement is required.")
            return
        self.accept()

    def values(self) -> AssetBindingEditorValues:
        """Return normalized editor values."""
        category = self.category_combo.currentData()
        if not isinstance(category, AssetCategory):
            raise GovernedAssetResolutionError("A valid asset category is required")
        return AssetBindingEditorValues(
            sequence_number=self.sequence_spin.value(),
            role=self.role_edit.text().strip(),
            requirement=self.requirement_edit.toPlainText().strip(),
            expected_category=category,
            asset_id=str(self.asset_combo.currentData() or "").strip().upper(),
            notes=self.notes_edit.toPlainText().strip(),
        )


class GovernedAssetResolverDialog(QDialog):
    """Resolve authoritative project assets beneath one current Ready Shot."""

    def __init__(
        self,
        service: GovernedAssetResolutionService,
        shot: ShotPlan,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.shot_id = shot.shot_id
        self.setObjectName("governedAssetResolverDialog")
        self.setWindowTitle(f"Asset Resolver — {shot.shot_id} — {shot.title}")
        self.setMinimumSize(920, 560)
        self.resize(1220, 760)

        root = QVBoxLayout(self)
        self.upstream_label = QLabel(self)
        self.upstream_label.setObjectName("assetResolverUpstreamStatus")
        self.upstream_label.setWordWrap(True)
        root.addWidget(self.upstream_label)
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("assetResolverSummary")
        root.addWidget(self.summary_label)

        guidance = QLabel(
            "Declare the production assets required by this Shot and bind each requirement to an existing "
            "approved project asset. This phase does not author new assets, camera plans or lighting plans.",
            self,
        )
        guidance.setWordWrap(True)
        root.addWidget(guidance)

        toolbar = QHBoxLayout()
        self.new_button = QPushButton("New Requirement", self)
        self.edit_button = QPushButton("Edit", self)
        self.delete_button = QPushButton("Delete Draft", self)
        self.ready_button = QPushButton("Mark Ready", self)
        self.draft_button = QPushButton("Return to Draft", self)
        self.up_button = QPushButton("Move Up", self)
        self.down_button = QPushButton("Move Down", self)
        for button in (
            self.new_button,
            self.edit_button,
            self.delete_button,
            self.ready_button,
            self.draft_button,
            self.up_button,
            self.down_button,
        ):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 8, self)
        self.table.setObjectName("governedAssetResolverTable")
        self.table.setHorizontalHeaderLabels(
            [
                "Binding",
                "Role",
                "Category",
                "Requirement",
                "Asset",
                "Resolution",
                "Governance",
                "Notes",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        close_buttons.rejected.connect(self.reject)
        root.addWidget(close_buttons)

        self.new_button.clicked.connect(self._new)
        self.edit_button.clicked.connect(self._edit)
        self.delete_button.clicked.connect(self._delete)
        self.ready_button.clicked.connect(self._mark_ready)
        self.draft_button.clicked.connect(self._return_to_draft)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))
        self.table.itemSelectionChanged.connect(self._update_actions)
        self.table.itemDoubleClicked.connect(lambda _item: self._edit())
        self.refresh()

    def refresh(self) -> None:
        """Reload current governed bindings and dependency readiness."""
        shot = self.service.shots.plan(self.shot_id)
        if shot is None:
            self.upstream_label.setText("Shot Plan is unavailable.")
            self.table.setRowCount(0)
            self._update_actions()
            return
        shot_ready = self.service.shots.is_production_ready(shot)
        self.upstream_label.setText(
            "Upstream Shot: Ready and current — Asset Resolution is enabled."
            if shot_ready
            else "Upstream Shot is not production-ready. Existing bindings remain visible but cannot advance."
        )
        bindings = self.service.list_bindings(shot_id=self.shot_id)
        ready_count = sum(1 for binding in bindings if self.service.is_production_ready(binding))
        self.summary_label.setText(
            f"Asset requirements: {len(bindings)} declared • {ready_count} production-ready • "
            f"{len(bindings) - ready_count} unresolved, Draft or stale"
        )
        self.table.setRowCount(len(bindings))
        for row, binding in enumerate(bindings):
            resolution = self.service.resolution(binding)
            resolution_status = "Unbound"
            if resolution is not None:
                resolution_status = resolution.status.value.title()
                if binding.asset_id and not self.service.is_asset_current(binding):
                    resolution_status += " / Changed"
            governance = binding.status.value.title()
            if not self.service.is_upstream_current(binding):
                governance += " / Shot Stale"
            elif binding.status is AssetBindingStatus.READY and not self.service.is_asset_current(binding):
                governance += " / Asset Stale"
            values = (
                binding.binding_id,
                binding.role,
                binding.expected_category.value.title(),
                binding.requirement,
                binding.asset_id or "—",
                resolution_status,
                governance,
                binding.notes,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, binding.binding_id)
                self.table.setItem(row, column, item)
        self._update_actions()

    def _selected(self) -> ShotAssetBinding | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        binding_id = item.data(Qt.ItemDataRole.UserRole)
        return self.service.binding(str(binding_id)) if binding_id else None

    def _update_actions(self) -> None:
        shot = self.service.shots.plan(self.shot_id)
        shot_ready = shot is not None and self.service.shots.is_production_ready(shot)
        binding = self._selected()
        draft = binding is not None and binding.status is AssetBindingStatus.DRAFT
        ready = binding is not None and binding.status is AssetBindingStatus.READY
        self.new_button.setEnabled(shot_ready)
        self.edit_button.setEnabled(shot_ready and draft)
        self.delete_button.setEnabled(draft)
        self.ready_button.setEnabled(shot_ready and draft)
        self.draft_button.setEnabled(ready)
        row = self.table.currentRow()
        self.up_button.setEnabled(binding is not None and row > 0)
        self.down_button.setEnabled(
            binding is not None
            and row >= 0
            and row < len(self.service.list_bindings(shot_id=self.shot_id)) - 1
        )

    def _new(self) -> None:
        shot = self.service.shots.plan(self.shot_id)
        if shot is None or not self.service.shots.is_production_ready(shot):
            return
        dialog = AssetBindingEditorDialog(self.service, shot, parent=self)
        dialog.sequence_spin.setValue(self.service.next_sequence_number(self.shot_id))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            binding = self.service.create(
                shot_id=self.shot_id,
                sequence_number=values.sequence_number,
                role=values.role,
                requirement=values.requirement,
                expected_category=values.expected_category,
                asset_id=values.asset_id,
                notes=values.notes,
            )
        except GovernedAssetResolutionError as exc:
            QMessageBox.warning(self, "Asset Resolver", str(exc))
            return
        self.refresh()
        self._select_identity(binding.binding_id)

    def _edit(self) -> None:
        binding = self._selected()
        shot = self.service.shots.plan(self.shot_id)
        if binding is None or shot is None or binding.status is not AssetBindingStatus.DRAFT:
            return
        dialog = AssetBindingEditorDialog(self.service, shot, binding, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        try:
            updated = self.service.update(
                binding.binding_id,
                role=values.role,
                requirement=values.requirement,
                expected_category=values.expected_category,
                asset_id=values.asset_id,
                notes=values.notes,
            )
        except GovernedAssetResolutionError as exc:
            QMessageBox.warning(self, "Asset Resolver", str(exc))
            return
        self.refresh()
        self._select_identity(updated.binding_id)

    def _delete(self) -> None:
        binding = self._selected()
        if binding is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Asset Requirement",
            f"Delete draft {binding.binding_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer is not QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.delete(binding.binding_id)
        except GovernedAssetResolutionError as exc:
            QMessageBox.warning(self, "Asset Resolver", str(exc))
            return
        self.refresh()

    def _mark_ready(self) -> None:
        binding = self._selected()
        if binding is None:
            return
        try:
            self.service.mark_ready(binding.binding_id)
        except GovernedAssetResolutionError as exc:
            QMessageBox.warning(self, "Asset Resolver", str(exc))
            return
        self.refresh()

    def _return_to_draft(self) -> None:
        binding = self._selected()
        if binding is None:
            return
        try:
            self.service.return_to_draft(binding.binding_id)
        except GovernedAssetResolutionError as exc:
            QMessageBox.warning(self, "Asset Resolver", str(exc))
            return
        self.refresh()

    def _move(self, offset: int) -> None:
        binding = self._selected()
        if binding is None:
            return
        bindings = list(self.service.list_bindings(shot_id=self.shot_id))
        index = next(
            (i for i, item in enumerate(bindings) if item.binding_id == binding.binding_id),
            -1,
        )
        target = index + offset
        if index < 0 or target < 0 or target >= len(bindings):
            return
        bindings[index], bindings[target] = bindings[target], bindings[index]
        try:
            self.service.reorder_shot(
                self.shot_id,
                tuple(item.binding_id for item in bindings),
            )
        except GovernedAssetResolutionError as exc:
            QMessageBox.warning(self, "Asset Resolver", str(exc))
            return
        self.refresh()
        self._select_identity(binding.binding_id)

    def _select_identity(self, binding_id: str) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.text() == binding_id:
                self.table.selectRow(row)
                return
