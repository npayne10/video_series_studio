"""Phase 19.4 Production Planning workspace for canonical Production Packages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.action_performance import (
    ActionPerformanceCompilerService,
    ActionPerformanceError,
    ActionPerformanceStatus,
)
from vscs.application.production_package import ProductionPackage, ProductionPackageService
from vscs.application.projects import ProjectService


class ProductionPackageWorkspace(QWidget):
    """Visible Phase 19.4 workspace rooted in current approved Production Packages."""

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        action_performance: ActionPerformanceCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.projects = projects
        self.packages = packages
        self.action_performance = action_performance
        self._selected_shot_id: str | None = None

        root = QVBoxLayout(self)
        title = QLabel("Production Planning", self)
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        root.addWidget(title)
        intro = QLabel(
            "Compile approved Shot planning into the canonical Production Package. "
            "Production intent remains provider-neutral; AI-specific prompts are generated later.",
            self,
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        root.addWidget(splitter, 1)

        left = QWidget(splitter)
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("Current approved Shots", left))
        self.package_table = QTableWidget(0, 4, left)
        self.package_table.setHorizontalHeaderLabels(("Shot", "Production Package", "Action", "Source"))
        self.package_table.horizontalHeader().setStretchLastSection(True)
        self.package_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.package_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        left_layout.addWidget(self.package_table, 1)
        self.refresh_button = QPushButton("Refresh", left)
        left_layout.addWidget(self.refresh_button)
        splitter.addWidget(left)

        right = QWidget(splitter)
        right_layout = QVBoxLayout(right)
        self.package_summary = QLabel("Select an approved Shot.", right)
        self.package_summary.setWordWrap(True)
        right_layout.addWidget(self.package_summary)

        action_group = QGroupBox("Action & Performance", right)
        action_layout = QVBoxLayout(action_group)
        guidance = QLabel(
            "Describe the actual temporal story of this Shot: who does what, in what order, "
            "what is spoken, how characters react, and the state in which the Shot ends.",
            action_group,
        )
        guidance.setWordWrap(True)
        action_layout.addWidget(guidance)

        form = QFormLayout()
        self.temporal_narrative = QTextEdit(action_group)
        self.temporal_narrative.setPlaceholderText(
            "Example: James descends the stairs, notices Cheryl at the viewport, walks over to her..."
        )
        self.spoken_content = QTextEdit(action_group)
        self.spoken_content.setMaximumHeight(100)
        self.performance_direction = QTextEdit(action_group)
        self.performance_direction.setMaximumHeight(90)
        self.opening_state = QTextEdit(action_group)
        self.opening_state.setMaximumHeight(70)
        self.closing_state = QTextEdit(action_group)
        self.closing_state.setMaximumHeight(70)
        self.timing_notes = QTextEdit(action_group)
        self.timing_notes.setMaximumHeight(70)
        form.addRow("Temporal narrative", self.temporal_narrative)
        form.addRow("Spoken content / dialogue", self.spoken_content)
        form.addRow("Performance direction", self.performance_direction)
        form.addRow("Opening state", self.opening_state)
        form.addRow("Closing state", self.closing_state)
        form.addRow("Timing notes", self.timing_notes)
        action_layout.addLayout(form)

        actions = QHBoxLayout()
        self.create_button = QPushButton("Create from Shot", action_group)
        self.save_button = QPushButton("Save Draft", action_group)
        self.ready_button = QPushButton("Mark Ready & Compile", action_group)
        self.draft_button = QPushButton("Return to Draft", action_group)
        actions.addWidget(self.create_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.ready_button)
        actions.addWidget(self.draft_button)
        actions.addStretch(1)
        action_layout.addLayout(actions)
        right_layout.addWidget(action_group, 1)

        future = QLabel(
            "Later Phase 19.4 compilers will add Asset, Camera, Lighting, Continuity, Style, "
            "Universal Description, Provider Output and Validation views to this same workspace.",
            right,
        )
        future.setWordWrap(True)
        right_layout.addWidget(future)
        splitter.addWidget(right)
        splitter.setSizes((480, 820))

        self.refresh_button.clicked.connect(self.refresh)
        self.package_table.itemSelectionChanged.connect(self._selection_changed)
        self.create_button.clicked.connect(self._create)
        self.save_button.clicked.connect(self._save)
        self.ready_button.clicked.connect(self._mark_ready)
        self.draft_button.clicked.connect(self._return_to_draft)
        self._set_editor_enabled(False)
        self.refresh()

    def refresh(self) -> None:
        """Rebuild current Production Package rows from approved Phase 19.3 handoffs."""
        selected = self._selected_shot_id
        rows: list[ProductionPackage] = []
        if self.projects.is_project_open:
            for integrated in self.packages.planning.list_packages():
                if self.packages.planning.is_current(integrated):
                    rows.append(self.packages.materialize(integrated.shot_id))
        self.package_table.setRowCount(len(rows))
        selected_row = -1
        for row, package in enumerate(rows):
            draft = self.action_performance.draft(package.shot_id)
            if draft is None:
                action_state = "Not started"
            elif draft.status is ActionPerformanceStatus.READY and self.action_performance.is_current(draft):
                action_state = "Ready / Compiled"
            elif not self.action_performance.is_current(draft):
                action_state = f"{draft.status.value.title()} / Stale"
            else:
                action_state = draft.status.value.title()
            values = (
                package.shot_id,
                package.package_id,
                action_state,
                package.provenance.integrated_package_id,
            )
            for column, value in enumerate(values):
                self.package_table.setItem(row, column, QTableWidgetItem(value))
            if package.shot_id == selected:
                selected_row = row
        if selected_row >= 0:
            self.package_table.selectRow(selected_row)
        elif rows:
            self.package_table.selectRow(0)
        else:
            self._selected_shot_id = None
            self.package_summary.setText(
                "No current approved Integrated Planning Packages are available. "
                "Complete Planning Review for a Shot first."
            )
            self._clear_editor()
            self._set_editor_enabled(False)

    def _selection_changed(self) -> None:
        row = self.package_table.currentRow()
        if row < 0:
            return
        item = self.package_table.item(row, 0)
        if item is None:
            return
        self._selected_shot_id = item.text()
        package = self.packages.current_package(self._selected_shot_id)
        if package is None:
            return
        self.package_summary.setText(
            f"<b>{package.shot_id}</b><br>Production Package: {package.package_id}<br>"
            f"Status: {package.status.value.title()} &nbsp; | &nbsp; "
            f"Planning source: {package.provenance.integrated_package_id}"
        )
        self._load_draft()

    def _load_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        draft = self.action_performance.draft(self._selected_shot_id)
        if draft is None:
            self._clear_editor()
            self.create_button.setEnabled(True)
            self.save_button.setEnabled(False)
            self.ready_button.setEnabled(False)
            self.draft_button.setEnabled(False)
            self._fields_read_only(True)
            return
        self.temporal_narrative.setPlainText(draft.temporal_narrative)
        self.spoken_content.setPlainText(draft.spoken_content)
        self.performance_direction.setPlainText(draft.performance_direction)
        self.opening_state.setPlainText(draft.opening_state)
        self.closing_state.setPlainText(draft.closing_state)
        self.timing_notes.setPlainText(draft.timing_notes)
        stale = not self.action_performance.is_current(draft)
        ready = draft.status is ActionPerformanceStatus.READY
        self.create_button.setEnabled(False)
        self.save_button.setEnabled(not ready and not stale)
        self.ready_button.setEnabled(not ready and not stale and bool(draft.temporal_narrative.strip()))
        self.draft_button.setEnabled(ready)
        self._fields_read_only(ready or stale)

    def _create(self) -> None:
        if self._selected_shot_id is None:
            return
        self._run(lambda: self.action_performance.create_from_current_package(self._selected_shot_id))

    def _save(self) -> None:
        if self._selected_shot_id is None:
            return
        self._run(
            lambda: self.action_performance.save(
                self._selected_shot_id,
                temporal_narrative=self.temporal_narrative.toPlainText(),
                spoken_content=self.spoken_content.toPlainText(),
                performance_direction=self.performance_direction.toPlainText(),
                opening_state=self.opening_state.toPlainText(),
                closing_state=self.closing_state.toPlainText(),
                timing_notes=self.timing_notes.toPlainText(),
            )
        )

    def _mark_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        self._save()
        self._run(lambda: self.action_performance.mark_ready(self._selected_shot_id))

    def _return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        self._run(lambda: self.action_performance.return_to_draft(self._selected_shot_id))

    def _run(self, action: object) -> None:
        try:
            action()  # type: ignore[operator]
        except ActionPerformanceError as exc:
            QMessageBox.warning(self, "Action & Performance", str(exc))
        self.refresh()

    def _set_editor_enabled(self, enabled: bool) -> None:
        for button in (self.create_button, self.save_button, self.ready_button, self.draft_button):
            button.setEnabled(enabled)
        self._fields_read_only(not enabled)

    def _fields_read_only(self, value: bool) -> None:
        for field in (
            self.temporal_narrative,
            self.spoken_content,
            self.performance_direction,
            self.opening_state,
            self.closing_state,
            self.timing_notes,
        ):
            field.setReadOnly(value)

    def _clear_editor(self) -> None:
        for field in (
            self.temporal_narrative,
            self.spoken_content,
            self.performance_direction,
            self.opening_state,
            self.closing_state,
            self.timing_notes,
        ):
            field.clear()
