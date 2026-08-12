"""Continuity Compiler extension for the Phase 19.4 Production Planning workspace."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.action_performance import ActionPerformanceCompilerService
from vscs.application.asset_compiler import AssetCompilerService
from vscs.application.camera_compiler import CameraCompilerService
from vscs.application.continuity_compiler import (
    ContinuityCompilationStatus,
    ContinuityCompilerError,
    ContinuityCompilerService,
)
from vscs.application.lighting_compiler import LightingCompilerService
from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService

from .lighting_compiler_workspace import LightingCompilerWorkspace


class ContinuityCompilerWorkspace(LightingCompilerWorkspace):
    """Extend Production Planning with continuity-by-inheritance compilation."""

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        action_performance: ActionPerformanceCompilerService,
        asset_compiler: AssetCompilerService,
        camera_compiler: CameraCompilerService,
        lighting_compiler: LightingCompilerService,
        continuity_compiler: ContinuityCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        self.continuity_compiler = continuity_compiler
        super().__init__(
            projects,
            packages,
            action_performance,
            asset_compiler,
            camera_compiler,
            lighting_compiler,
            parent,
        )
        self.package_table.setColumnCount(8)
        self.package_table.setHorizontalHeaderLabels(
            (
                "Shot",
                "Production Package",
                "Action",
                "Assets",
                "Camera",
                "Lighting",
                "Continuity",
                "Source",
            )
        )
        self._build_continuity_tab()
        if hasattr(self, "footer_label"):
            self.footer_label.setText(
                "Later Phase 19.4 compilers will add Style, Universal Description, Provider Output "
                "and Validation views to this same workspace."
            )
        self.refresh()

    def _build_continuity_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Continuity Compiler", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Review inherited production state before compiling Continuity authority. Previous-Shot "
            "closing state is carried forward automatically; conflicts are exposed for user review "
            "rather than silently rewritten.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)

        self.continuity_status = QLabel("", group)
        self.continuity_status.setWordWrap(True)
        group_layout.addWidget(self.continuity_status)

        self.continuity_table = QTableWidget(0, 2, group)
        self.continuity_table.setHorizontalHeaderLabels(("Continuity field", "Resolved value"))
        self.continuity_table.horizontalHeader().setStretchLastSection(True)
        self.continuity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.continuity_table, 1)

        group_layout.addWidget(QLabel("Production review notes", group))
        self.continuity_notes = QTextEdit(group)
        self.continuity_notes.setMaximumHeight(90)
        self.continuity_notes.setPlaceholderText(
            "Optional user review notes. Final Continuity approval remains with the user."
        )
        group_layout.addWidget(self.continuity_notes)

        actions = QHBoxLayout()
        self.continuity_create_button = QPushButton("Create from Inherited State", group)
        self.continuity_refresh_button = QPushButton("Refresh Inherited State", group)
        self.continuity_save_button = QPushButton("Save Review Notes", group)
        self.continuity_ready_button = QPushButton("Mark Ready & Compile", group)
        self.continuity_draft_button = QPushButton("Return to Draft", group)
        for button in (
            self.continuity_create_button,
            self.continuity_refresh_button,
            self.continuity_save_button,
            self.continuity_ready_button,
            self.continuity_draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Continuity")

        self.continuity_create_button.clicked.connect(self._continuity_create)
        self.continuity_refresh_button.clicked.connect(self._continuity_refresh)
        self.continuity_save_button.clicked.connect(self._continuity_save)
        self.continuity_ready_button.clicked.connect(self._continuity_ready)
        self.continuity_draft_button.clicked.connect(self._continuity_return_to_draft)
        self._set_continuity_editor_enabled(False)

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "continuity_table"):
            return
        self.package_table.setColumnCount(8)
        self.package_table.setHorizontalHeaderLabels(
            (
                "Shot",
                "Production Package",
                "Action",
                "Assets",
                "Camera",
                "Lighting",
                "Continuity",
                "Source",
            )
        )
        for row in range(self.package_table.rowCount()):
            shot = self.package_table.item(row, 0)
            source = self.package_table.item(row, 6)
            if source is not None:
                self.package_table.setItem(row, 7, QTableWidgetItem(source.text()))
            if shot is not None:
                self.package_table.setItem(
                    row,
                    6,
                    QTableWidgetItem(self._continuity_state(shot.text())),
                )
        self._load_continuity_draft()

    def _selection_changed(self) -> None:
        super()._selection_changed()
        if hasattr(self, "continuity_table"):
            self._load_continuity_draft()

    def _continuity_state(self, shot_id: str) -> str:
        draft = self.continuity_compiler.draft(shot_id)
        if draft is None:
            return "Not started"
        if (
            draft.status is ContinuityCompilationStatus.READY
            and self.continuity_compiler.is_current(draft)
        ):
            return "Ready / Compiled"
        if not self.continuity_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

    def _load_continuity_draft(self) -> None:
        if not hasattr(self, "continuity_table") or self._selected_shot_id is None:
            return
        draft = self.continuity_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.continuity_status.setText(
                "No Continuity Compiler Draft exists yet. Create one from current and inherited "
                "production state."
            )
            self.continuity_table.setRowCount(0)
            self.continuity_notes.clear()
            self.continuity_create_button.setEnabled(True)
            self.continuity_refresh_button.setEnabled(False)
            self.continuity_save_button.setEnabled(False)
            self.continuity_ready_button.setEnabled(False)
            self.continuity_draft_button.setEnabled(False)
            self.continuity_notes.setReadOnly(True)
            return

        continuity = draft.continuity_value()
        self._populate_continuity_table(continuity)
        self.continuity_notes.setPlainText(draft.production_notes)
        stale = not self.continuity_compiler.is_current(draft)
        ready = draft.status is ContinuityCompilationStatus.READY
        conflicts = continuity.get("continuity_conflicts", [])
        conflict_count = len(conflicts) if isinstance(conflicts, list) else 0
        if stale:
            self.continuity_status.setText(
                "Continuity compilation is stale because current or previous-Shot production state "
                "changed. Refresh Inherited State to recalculate continuity while preserving human "
                "review notes."
            )
        elif ready:
            self.continuity_status.setText(
                "Continuity authority is Ready and compiled into the current Production Package."
            )
        elif conflict_count:
            self.continuity_status.setText(
                f"Continuity Draft is current with {conflict_count} inherited-state conflict(s). "
                "Review the resolved state before final approval."
            )
        else:
            source = draft.previous_shot_id or "series entry"
            self.continuity_status.setText(
                f"Continuity Draft is current. Opening state was resolved from {source}; final "
                "approval remains with the user."
            )
        self.continuity_create_button.setEnabled(False)
        self.continuity_refresh_button.setEnabled(stale and not ready)
        self.continuity_save_button.setEnabled(not stale and not ready)
        self.continuity_ready_button.setEnabled(not stale and not ready)
        self.continuity_draft_button.setEnabled(ready)
        self.continuity_notes.setReadOnly(stale or ready)

    def _populate_continuity_table(self, continuity: dict[str, Any]) -> None:
        fields = (
            "previous_shot_id",
            "previous_closing_state",
            "current_opening_state",
            "effective_opening_state",
            "current_closing_state",
            "previous_asset_ids",
            "current_asset_ids",
            "previous_screen_direction",
            "current_screen_direction",
            "previous_lighting_continuity",
            "current_lighting_continuity",
            "inheritance_mode",
            "continuity_conflicts",
        )
        self.continuity_table.setRowCount(len(fields))
        for row, key in enumerate(fields):
            value = continuity.get(key, "")
            if isinstance(value, list | tuple):
                text = "; ".join(str(item) for item in value)
            elif isinstance(value, dict):
                text = json_summary(value)
            else:
                text = str(value)
            self.continuity_table.setItem(
                row,
                0,
                QTableWidgetItem(key.replace("_", " ").title()),
            )
            self.continuity_table.setItem(row, 1, QTableWidgetItem(text))

    def _continuity_create(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_continuity(lambda: self.continuity_compiler.create_from_current_package(shot_id))

    def _continuity_refresh(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_continuity(lambda: self.continuity_compiler.rebase_to_current_package(shot_id))

    def _continuity_save(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_continuity(
            lambda: self.continuity_compiler.save_notes(
                shot_id,
                self.continuity_notes.toPlainText(),
            )
        )

    def _continuity_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        try:
            self.continuity_compiler.save_notes(shot_id, self.continuity_notes.toPlainText())
            self.continuity_compiler.mark_ready(shot_id)
        except ContinuityCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Continuity Compiler", str(exc))
        self.refresh()

    def _continuity_return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_continuity(lambda: self.continuity_compiler.return_to_draft(shot_id))

    def _run_continuity(self, action: Any) -> None:
        try:
            action()
        except ContinuityCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Continuity Compiler", str(exc))
        self.refresh()

    def _set_continuity_editor_enabled(self, enabled: bool) -> None:
        for button in (
            self.continuity_create_button,
            self.continuity_refresh_button,
            self.continuity_save_button,
            self.continuity_ready_button,
            self.continuity_draft_button,
        ):
            button.setEnabled(enabled)
        self.continuity_notes.setReadOnly(not enabled)


def json_summary(value: dict[str, Any]) -> str:
    """Produce a compact deterministic UI summary for structured continuity context."""
    return "; ".join(f"{key}={value[key]}" for key in sorted(value))
