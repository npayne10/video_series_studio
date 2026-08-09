"""Production-contract UI refactoring for Canonical Asset Profiles.

Phase 18.2.11.2.9 keeps presentation concerns thin: the CAP workspace consumes
ProductionProjectionService and does not recalculate readiness, reference lifecycle,
or canonical production rules in the UI.
"""

from __future__ import annotations

from types import MethodType
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps import CAPError, ProductionProjectionService
from vscs.domain.caps import ProductionProjection, ReadinessSeverity


class ProductionProjectionDialog(QDialog):
    """Read-only inspection of the authoritative downstream CAP projection."""

    def __init__(self, projection: ProductionProjection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.projection = projection
        self.setObjectName("productionProjectionDialog")
        self.setWindowTitle(f"Production Projection — {projection.identity.asset_id}")
        self.setMinimumSize(640, 480)
        self._size_to_available_screen()

        identity = QFormLayout()
        identity.addRow("Asset ID", QLabel(projection.identity.asset_id))
        identity.addRow("Canonical name", QLabel(projection.identity.canonical_name))
        identity.addRow(
            "Category",
            QLabel(projection.identity.category.value.replace("_", " ").title()),
        )
        identity.addRow("CAP version", QLabel(projection.source_cap_version))
        identity.addRow("Projection schema", QLabel(projection.schema_version))
        identity.addRow("Checksum", self._wrapped(projection.checksum()))

        identity_box = QGroupBox("Canonical Identity")
        identity_box.setLayout(identity)

        readiness = QFormLayout()
        readiness.addRow("Overall", QLabel(f"{projection.readiness.overall_score}%"))
        readiness.addRow("Identity", QLabel(self._assessment(projection.readiness.identity)))
        readiness.addRow("References", QLabel(self._assessment(projection.readiness.references)))
        readiness.addRow("Generation", QLabel(self._assessment(projection.readiness.generation)))
        readiness.addRow("Production", QLabel(self._assessment(projection.readiness.production)))
        readiness_box = QGroupBox("Authoritative Readiness")
        readiness_box.setLayout(readiness)

        canonical = QFormLayout()
        canonical.addRow(
            "Canonical description",
            self._wrapped(projection.canonical_description or "—"),
        )
        canonical.addRow("Visual identity", self._wrapped(projection.visual_identity or "—"))
        canonical.addRow(
            "Production guidance",
            self._wrapped(projection.production_guidance or "—"),
        )
        canonical.addRow("Structured facts", QLabel(str(len(projection.facts))))
        canonical.addRow(
            "Functional capabilities",
            QLabel(str(len(projection.functional_identity))),
        )
        canonical.addRow("Canonical constraints", QLabel(str(len(projection.constraints))))
        canonical_box = QGroupBox("Production Contract")
        canonical_box.setLayout(canonical)

        self.references = QTableWidget(0, 6)
        self.references.setObjectName("productionProjectionReferences")
        self.references.setHorizontalHeaderLabels(
            ("Reference ID", "Family", "View", "Lifecycle", "Version", "File")
        )
        self.references.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.references.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.references.setAlternatingRowColors(True)
        self.references.setMinimumHeight(220)
        self.references.setRowCount(len(projection.references))
        for row, reference in enumerate(projection.references):
            values = (
                reference.reference_id,
                reference.family.value.replace("_", " ").title(),
                reference.view.value.replace("_", " ").title(),
                reference.lifecycle.value.title(),
                reference.version,
                reference.file_path,
            )
            for column, value in enumerate(values):
                self.references.setItem(row, column, QTableWidgetItem(value))
        self.references.horizontalHeader().setStretchLastSection(True)

        gaps = self._wrapped(self._gap_text(projection))
        gaps.setObjectName("productionProjectionGaps")
        gaps_box = QGroupBox("Blocking Issues and Warnings")
        gaps_layout = QVBoxLayout(gaps_box)
        gaps_layout.addWidget(gaps)

        top = QHBoxLayout()
        top.addWidget(identity_box, 1)
        top.addWidget(readiness_box, 1)

        content = QWidget()
        content.setObjectName("productionProjectionScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.addLayout(top)
        content_layout.addWidget(canonical_box)
        content_layout.addWidget(QLabel("Published Production References (Approved / Locked only)"))
        content_layout.addWidget(self.references)
        content_layout.addWidget(gaps_box)
        content_layout.addStretch(1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("productionProjectionScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setWidget(content)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(buttons)

    def _size_to_available_screen(self) -> None:
        """Choose an initial size that always fits inside the current desktop."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(900, 680)
            return
        available = screen.availableGeometry()
        width = min(980, max(640, int(available.width() * 0.85)))
        height = min(760, max(480, int(available.height() * 0.85)))
        self.resize(width, height)

    @staticmethod
    def _wrapped(text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _assessment(assessment: Any) -> str:
        return f"{assessment.state.value.replace('_', ' ').upper()} — {assessment.score}%"

    @staticmethod
    def _gap_text(projection: ProductionProjection) -> str:
        lines: list[str] = []
        for assessment in projection.readiness.assessments:
            for gap in assessment.gaps:
                marker = "BLOCK" if gap.severity is ReadinessSeverity.BLOCKING else "WARN"
                lines.append(f"• [{marker}] {gap.message}")
        return "\n".join(lines) if lines else "No readiness gaps."


def install_cap_editor_contract_refactoring() -> None:
    """Retire redundant generation UI and clarify governed reference ownership.

    The older CAP editor extension may install a `Generate Canonical Images…` button.
    Derived production views are now owned by Phase 18.2.11.2.5+ and therefore that
    legacy generator is hidden when present. External-reference import remains valid.
    """
    from vscs.presentation.widgets import cap_manager

    editor = cap_manager.CAPEditorDialog
    if getattr(editor, "_phase_18_2_11_2_9_installed", False):
        return
    original_init = editor.__init__

    def contract_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.setMinimumSize(max(self.minimumWidth(), 960), max(self.minimumHeight(), 760))
        self.setWindowTitle(
            "Canonical Profile — Production Contract" if self.profile else "New Canonical Profile"
        )

        legacy_generate = getattr(self, "generate_reference_button", None)
        if legacy_generate is not None:
            legacy_generate.hide()
            legacy_generate.setEnabled(False)
            legacy_generate.setToolTip(
                "Retired by Phase 18.2.11.2.9. Use Generate Production References from the Canonical Profiles workspace."
            )

        if hasattr(self, "add_reference_button"):
            self.add_reference_button.setText("Import External Reference…")
            self.add_reference_button.setToolTip(
                "Import an externally supplied supporting reference. MASTER revisions are governed from Assets; derived views are generated from the Canonical Profiles workspace."
            )
        if hasattr(self, "edit_reference_button"):
            self.edit_reference_button.setToolTip(
                "Edit metadata only when the selected reference lifecycle permits editing."
            )
        if hasattr(self, "remove_reference_button"):
            self.remove_reference_button.setToolTip(
                "Remove only an unlocked reference. Approved/Locked reference lifecycle is governed by the Reference Library."
            )

        guidance = QLabel(
            "Production Contract: the approved ChatGPT MASTER is governed from Assets. "
            "Use Generate Production References in the Canonical Profiles workspace for required derived views. "
            "Reference approval, locking, rejection and archival remain governed lifecycle operations."
        )
        guidance.setObjectName("capProductionContractGuidance")
        guidance.setWordWrap(True)
        guidance.setStyleSheet("font-weight: 600;")
        self.layout().insertWidget(0, guidance)

    editor.__init__ = contract_init
    editor._phase_18_2_11_2_9_installed = True


def install_cap_workspace_refactoring(
    cap_manager: QWidget,
    projection_service: ProductionProjectionService,
) -> QPushButton:
    """Refactor the CAP list into a production-contract status workspace."""
    table = cap_manager.table
    table.setColumnCount(8)
    table.setHorizontalHeaderLabels(
        (
            "Asset ID",
            "CAP Title",
            "Category",
            "Version",
            "Status",
            "Published References",
            "Readiness",
            "Production",
        )
    )
    table.setSortingEnabled(False)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)

    def refactored_refresh(self: Any) -> None:
        try:
            profiles = self.caps.list(
                query=self.search_input.text(), status=self.status_filter.currentData()
            )
        except CAPError as exc:
            self.table.setRowCount(0)
            self.summary_label.setText(str(exc))
            self._set_enabled(False)
            return
        self._set_enabled(True)
        self.table.setRowCount(len(profiles))
        ready_count = 0
        for row, profile in enumerate(profiles):
            try:
                projection = projection_service.project(profile.asset_id)
                category = projection.identity.category.value
                published = len(projection.references)
                readiness = f"{projection.readiness.overall_score}%"
                production = "READY" if projection.production_ready else "BLOCKED"
                if projection.production_ready:
                    ready_count += 1
                blocker_text = (
                    "\n".join(gap.message for gap in projection.readiness.blocking_gaps)
                    or "No production blockers"
                )
            except (RuntimeError, ValueError, CAPError):
                asset = self.caps.assets.get(profile.asset_id)
                category = asset.category.value
                published = 0
                readiness = "—"
                production = "BLOCKED"
                blocker_text = "Production projection is unavailable"

            values = (
                profile.asset_id,
                profile.title,
                category,
                profile.version,
                profile.status.value,
                str(published),
                readiness,
                production,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, profile.asset_id)
                if column in {6, 7}:
                    item.setToolTip(blocker_text)
                self.table.setItem(row, column, item)
        self.summary_label.setText(f"{len(profiles)} CAP(s) — {ready_count} production ready")
        update_projection_enabled()

    cap_manager.refresh = MethodType(refactored_refresh, cap_manager)

    projection_button = QPushButton("Production Projection")
    projection_button.setObjectName("capProductionProjectionButton")
    projection_button.setToolTip(
        "Inspect the immutable CAP projection published to Production Planning and downstream systems"
    )

    def show_projection() -> None:
        asset_id = cap_manager._selected_asset_id()
        if asset_id is None:
            QMessageBox.information(cap_manager, "Production Projection", "Select a CAP first.")
            return
        try:
            projection = projection_service.project(asset_id)
        except (RuntimeError, ValueError, CAPError) as exc:
            QMessageBox.critical(cap_manager, "Production Projection", str(exc))
            return
        ProductionProjectionDialog(projection, cap_manager).exec()

    def update_projection_enabled() -> None:
        projection_button.setEnabled(cap_manager._selected_asset_id() is not None)

    projection_button.clicked.connect(show_projection)
    table.itemSelectionChanged.connect(update_projection_enabled)
    controls = cap_manager.layout().itemAt(0).layout()
    if controls is not None:
        controls.insertWidget(max(0, controls.count() - 3), projection_button)

    cap_manager.production_projection_service = projection_service
    cap_manager.production_projection_button = projection_button
    update_projection_enabled()
    cap_manager.refresh()
    return projection_button
