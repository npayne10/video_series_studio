"""Phase 19.4 Production Planning workspace for canonical Production Packages."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

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
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.action_performance import (
    ActionPerformanceCompilerService,
    ActionPerformanceError,
    ActionPerformanceStatus,
)
from vscs.application.asset_compiler import (
    AssetCompilationStatus,
    AssetCompilerError,
    AssetCompilerService,
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
        asset_compiler: AssetCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.projects = projects
        self.packages = packages
        self.action_performance = action_performance
        self.asset_compiler = asset_compiler
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
        self.package_table = QTableWidget(0, 5, left)
        self.package_table.setHorizontalHeaderLabels(
            ("Shot", "Production Package", "Action", "Assets", "Source")
        )
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

        self.compiler_tabs = QTabWidget(right)
        right_layout.addWidget(self.compiler_tabs, 1)
        self._build_action_tab()
        self._build_asset_tab()

        future = QLabel(
            "Later Phase 19.4 compilers will add Camera, Lighting, Continuity, Style, "
            "Universal Description, Provider Output and Validation views to this same workspace.",
            right,
        )
        future.setWordWrap(True)
        right_layout.addWidget(future)
        splitter.addWidget(right)
        splitter.setSizes((500, 800))

        self.refresh_button.clicked.connect(self.refresh)
        self.package_table.itemSelectionChanged.connect(self._selection_changed)
        self.create_button.clicked.connect(self._create)
        self.refresh_source_button.clicked.connect(self._refresh_source)
        self.save_button.clicked.connect(self._save)
        self.ready_button.clicked.connect(self._mark_ready)
        self.draft_button.clicked.connect(self._return_to_draft)
        self.asset_create_button.clicked.connect(self._asset_create)
        self.asset_refresh_button.clicked.connect(self._asset_refresh_source)
        self.asset_save_button.clicked.connect(self._asset_save)
        self.asset_ready_button.clicked.connect(self._asset_mark_ready)
        self.asset_draft_button.clicked.connect(self._asset_return_to_draft)
        self._set_editor_enabled(False)
        self._set_asset_editor_enabled(False)
        self.refresh()

    def _build_action_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        action_group = QGroupBox("Action & Performance", tab)
        action_layout = QVBoxLayout(action_group)
        guidance = QLabel(
            "Describe the actual temporal story of this Shot: who does what, in what order, "
            "what is spoken, how characters react, and the state in which the Shot ends.",
            action_group,
        )
        guidance.setWordWrap(True)
        action_layout.addWidget(guidance)

        self.action_status = QLabel("", action_group)
        self.action_status.setWordWrap(True)
        action_layout.addWidget(self.action_status)

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
        self.refresh_source_button = QPushButton("Refresh from Current Shot", action_group)
        self.refresh_source_button.setToolTip(
            "Rebase this Draft onto the current Production Package while preserving authored content"
        )
        self.save_button = QPushButton("Save Draft", action_group)
        self.ready_button = QPushButton("Mark Ready & Compile", action_group)
        self.draft_button = QPushButton("Return to Draft", action_group)
        actions.addWidget(self.create_button)
        actions.addWidget(self.refresh_source_button)
        actions.addWidget(self.save_button)
        actions.addWidget(self.ready_button)
        actions.addWidget(self.draft_button)
        actions.addStretch(1)
        action_layout.addLayout(actions)
        layout.addWidget(action_group, 1)
        self.compiler_tabs.addTab(tab, "Action & Performance")

    def _build_asset_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        asset_group = QGroupBox("Asset Compiler", tab)
        asset_layout = QVBoxLayout(asset_group)
        guidance = QLabel(
            "Review the governed Shot asset bindings and canonical resolutions before compiling "
            "them into production Asset authority. This compiler does not invent or substitute assets.",
            asset_group,
        )
        guidance.setWordWrap(True)
        asset_layout.addWidget(guidance)

        self.asset_status = QLabel("", asset_group)
        self.asset_status.setWordWrap(True)
        asset_layout.addWidget(self.asset_status)

        self.asset_table = QTableWidget(0, 5, asset_group)
        self.asset_table.setHorizontalHeaderLabels(
            ("Binding", "Asset", "Role", "Requirement", "Canonical References")
        )
        self.asset_table.horizontalHeader().setStretchLastSection(True)
        self.asset_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.asset_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        asset_layout.addWidget(self.asset_table, 1)

        self.asset_notes = QTextEdit(asset_group)
        self.asset_notes.setMaximumHeight(90)
        self.asset_notes.setPlaceholderText(
            "Optional human review notes for production use; no asset identity is invented here."
        )
        asset_layout.addWidget(QLabel("Production review notes", asset_group))
        asset_layout.addWidget(self.asset_notes)

        actions = QHBoxLayout()
        self.asset_create_button = QPushButton("Create from Package", asset_group)
        self.asset_refresh_button = QPushButton("Refresh from Current Package", asset_group)
        self.asset_save_button = QPushButton("Save Review Notes", asset_group)
        self.asset_ready_button = QPushButton("Mark Ready & Compile", asset_group)
        self.asset_draft_button = QPushButton("Return to Draft", asset_group)
        actions.addWidget(self.asset_create_button)
        actions.addWidget(self.asset_refresh_button)
        actions.addWidget(self.asset_save_button)
        actions.addWidget(self.asset_ready_button)
        actions.addWidget(self.asset_draft_button)
        actions.addStretch(1)
        asset_layout.addLayout(actions)
        layout.addWidget(asset_group, 1)
        self.compiler_tabs.addTab(tab, "Assets")

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
            action_state = self._action_state(package.shot_id)
            asset_state = self._asset_state(package.shot_id)
            values = (
                package.shot_id,
                package.package_id,
                action_state,
                asset_state,
                package.provenance.integrated_package_id,
            )
            for column, value in enumerate(values):
                self.package_table.setItem(row, column, QTableWidgetItem(value))
            if package.shot_id == selected:
                selected_row = row
        if selected_row >= 0:
            self.package_table.selectRow(selected_row)
            self._selection_changed()
        elif rows:
            self.package_table.selectRow(0)
            self._selection_changed()
        else:
            self._selected_shot_id = None
            self.package_summary.setText(
                "No current approved Integrated Planning Packages are available. "
                "Complete Planning Review for a Shot first."
            )
            self.action_status.clear()
            self.asset_status.clear()
            self._clear_editor()
            self._clear_asset_editor()
            self._set_editor_enabled(False)
            self._set_asset_editor_enabled(False)

    def _action_state(self, shot_id: str) -> str:
        draft = self.action_performance.draft(shot_id)
        if draft is None:
            return "Not started"
        if draft.status is ActionPerformanceStatus.READY and self.action_performance.is_current(
            draft
        ):
            return "Ready / Compiled"
        if not self.action_performance.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

    def _asset_state(self, shot_id: str) -> str:
        draft = self.asset_compiler.draft(shot_id)
        if draft is None:
            return "Not started"
        if draft.status is AssetCompilationStatus.READY and self.asset_compiler.is_current(draft):
            return "Ready / Compiled"
        if not self.asset_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

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
        self._load_asset_draft()

    def _load_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        draft = self.action_performance.draft(self._selected_shot_id)
        if draft is None:
            self.action_status.setText(
                "No Action & Performance Draft exists yet. Create one from the current governed Shot."
            )
            self._clear_editor()
            self.create_button.setEnabled(True)
            self.refresh_source_button.setEnabled(False)
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
        if stale:
            self.action_status.setText(
                "Action & Performance is stale because its approved Planning source changed. "
                "Refresh from Current Shot to preserve this authored content and review it against "
                "the current Production Package before compiling."
            )
        elif ready:
            self.action_status.setText(
                "Action & Performance is Ready and compiled into the current Production Package."
            )
        else:
            self.action_status.setText(
                "Action & Performance Draft is current. Review, edit and mark it Ready when complete."
            )
        self.create_button.setEnabled(False)
        self.refresh_source_button.setEnabled(stale and not ready)
        self.save_button.setEnabled(not ready and not stale)
        self.ready_button.setEnabled(
            not ready and not stale and bool(draft.temporal_narrative.strip())
        )
        self.draft_button.setEnabled(ready)
        self._fields_read_only(ready or stale)

    def _load_asset_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        draft = self.asset_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.asset_status.setText(
                "No Asset Compiler Draft exists yet. Create one from the current Production Package."
            )
            self._clear_asset_editor()
            self.asset_create_button.setEnabled(True)
            self.asset_refresh_button.setEnabled(False)
            self.asset_save_button.setEnabled(False)
            self.asset_ready_button.setEnabled(False)
            self.asset_draft_button.setEnabled(False)
            self.asset_notes.setReadOnly(True)
            return
        self._populate_asset_table(draft.assets)
        self.asset_notes.setPlainText(draft.production_notes)
        stale = not self.asset_compiler.is_current(draft)
        ready = draft.status is AssetCompilationStatus.READY
        if stale:
            self.asset_status.setText(
                "Asset compilation is stale because governed Planning assets changed. Refresh from "
                "Current Package to load the current bindings while preserving human review notes."
            )
        elif ready:
            self.asset_status.setText(
                "Asset authority is Ready and compiled into the current Production Package."
            )
        else:
            count = len(draft.assets)
            self.asset_status.setText(
                f"Asset Compiler Draft is current with {count} governed asset binding(s). "
                "Review the canonical resolutions and mark it Ready when complete."
            )
        self.asset_create_button.setEnabled(False)
        self.asset_refresh_button.setEnabled(not ready)
        self.asset_save_button.setEnabled(not stale and not ready)
        self.asset_ready_button.setEnabled(not stale and not ready)
        self.asset_draft_button.setEnabled(ready)
        self.asset_notes.setReadOnly(stale or ready)

    def _populate_asset_table(self, assets: tuple[dict[str, Any], ...]) -> None:
        self.asset_table.setRowCount(len(assets))
        for row, item in enumerate(assets):
            binding = item.get("binding", {})
            resolution = item.get("resolution", {})
            if not isinstance(binding, dict):
                binding = {}
            if not isinstance(resolution, dict):
                resolution = {}
            values = (
                str(binding.get("binding_id", "")),
                str(resolution.get("asset_id") or binding.get("asset_id") or ""),
                str(binding.get("role", "")),
                str(binding.get("requirement", "")),
                self._canonical_reference_text(resolution),
            )
            for column, value in enumerate(values):
                self.asset_table.setItem(row, column, QTableWidgetItem(value))

    @staticmethod
    def _canonical_reference_text(resolution: dict[str, Any]) -> str:
        """Render current canonical reference authority from legacy or multi-reference contracts."""
        raw_references = resolution.get("canonical_references")
        if not isinstance(raw_references, list | tuple):
            raw_references = resolution.get("references")
        rendered: list[str] = []
        if isinstance(raw_references, list | tuple):
            for item in raw_references:
                if not isinstance(item, dict):
                    continue
                path = str(item.get("file_path") or item.get("canonical_reference") or "").strip()
                if not path:
                    continue
                role = str(item.get("role", "")).strip()
                text = f"{role}: {path}" if role else path
                if text not in rendered:
                    rendered.append(text)
        if rendered:
            return "; ".join(rendered)
        return str(resolution.get("canonical_reference") or "")

    def _create(self) -> None:
        if self._selected_shot_id is None:
            return
        self._run(
            lambda: self.action_performance.create_from_current_package(
                self._selected_shot_id or ""
            ),
            "Action & Performance",
        )

    def _refresh_source(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(
            lambda: self.action_performance.rebase_to_current_package(shot_id),
            "Action & Performance",
        )

    def _save(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(
            lambda: self.action_performance.save(
                shot_id,
                temporal_narrative=self.temporal_narrative.toPlainText(),
                spoken_content=self.spoken_content.toPlainText(),
                performance_direction=self.performance_direction.toPlainText(),
                opening_state=self.opening_state.toPlainText(),
                closing_state=self.closing_state.toPlainText(),
                timing_notes=self.timing_notes.toPlainText(),
            ),
            "Action & Performance",
        )

    def _mark_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._save()
        self._run(
            lambda: self.action_performance.mark_ready(shot_id),
            "Action & Performance",
        )

    def _return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(
            lambda: self.action_performance.return_to_draft(shot_id),
            "Action & Performance",
        )

    def _asset_create(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(
            lambda: self.asset_compiler.create_from_current_package(shot_id),
            "Asset Compiler",
        )

    def _asset_refresh_source(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(
            lambda: self.asset_compiler.rebase_to_current_package(shot_id),
            "Asset Compiler",
        )

    def _asset_save(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(
            lambda: self.asset_compiler.save_notes(shot_id, self.asset_notes.toPlainText()),
            "Asset Compiler",
        )

    def _asset_mark_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._asset_save()
        self._run(lambda: self.asset_compiler.mark_ready(shot_id), "Asset Compiler")

    def _asset_return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run(lambda: self.asset_compiler.return_to_draft(shot_id), "Asset Compiler")

    def _run(self, action: Callable[[], object], title: str) -> None:
        try:
            action()
        except (ActionPerformanceError, AssetCompilerError) as exc:
            QMessageBox.warning(self, title, str(exc))
        self.refresh()

    def _set_editor_enabled(self, enabled: bool) -> None:
        for button in (
            self.create_button,
            self.refresh_source_button,
            self.save_button,
            self.ready_button,
            self.draft_button,
        ):
            button.setEnabled(enabled)
        self._fields_read_only(not enabled)

    def _set_asset_editor_enabled(self, enabled: bool) -> None:
        for button in (
            self.asset_create_button,
            self.asset_refresh_button,
            self.asset_save_button,
            self.asset_ready_button,
            self.asset_draft_button,
        ):
            button.setEnabled(enabled)
        self.asset_notes.setReadOnly(not enabled)

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

    def _clear_asset_editor(self) -> None:
        self.asset_table.setRowCount(0)
        self.asset_notes.clear()
