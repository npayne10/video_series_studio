"""Style Compiler extension for the Phase 19.4 Production Planning workspace."""

from __future__ import annotations

import json
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
from vscs.application.continuity_compiler import ContinuityCompilerService
from vscs.application.lighting_compiler import LightingCompilerService
from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService
from vscs.application.style_compiler import (
    StyleCompilationStatus,
    StyleCompilerError,
    StyleCompilerService,
)

from .continuity_compiler_workspace import ContinuityCompilerWorkspace


class StyleCompilerWorkspace(ContinuityCompilerWorkspace):
    """Extend Production Planning with governed provider-neutral Style authority."""

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
        parent: QWidget | None = None,
    ) -> None:
        self.style_compiler = style_compiler
        super().__init__(
            projects,
            packages,
            action_performance,
            asset_compiler,
            camera_compiler,
            lighting_compiler,
            continuity_compiler,
            parent,
        )
        self.package_table.setColumnCount(9)
        self.package_table.setHorizontalHeaderLabels(self._headers())
        self._build_style_tab()
        if hasattr(self, "footer_label"):
            self.footer_label.setText(
                "Later Phase 19.4 compilers will add Universal Description, Provider Output and "
                "Validation views to this same workspace."
            )
        self.refresh()

    @staticmethod
    def _headers() -> tuple[str, ...]:
        return (
            "Shot",
            "Production Package",
            "Action",
            "Assets",
            "Camera",
            "Lighting",
            "Continuity",
            "Style",
            "Source",
        )

    def _build_style_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Style Compiler", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Review the governed visual language assembled from approved Shot, Asset, Camera, "
            "Lighting, Environment and Continuity authority. The compiler does not invent a new "
            "aesthetic and remains provider-neutral.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)

        self.style_status = QLabel("", group)
        self.style_status.setWordWrap(True)
        group_layout.addWidget(self.style_status)

        self.style_table = QTableWidget(0, 2, group)
        self.style_table.setHorizontalHeaderLabels(("Style field", "Governed value"))
        self.style_table.horizontalHeader().setStretchLastSection(True)
        self.style_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.style_table, 1)

        group_layout.addWidget(QLabel("Production review notes", group))
        self.style_notes = QTextEdit(group)
        self.style_notes.setMaximumHeight(90)
        self.style_notes.setPlaceholderText(
            "Optional user review notes. Final Style approval remains with the user."
        )
        group_layout.addWidget(self.style_notes)

        actions = QHBoxLayout()
        self.style_create_button = QPushButton("Create from Governed State", group)
        self.style_refresh_button = QPushButton("Refresh from Current Package", group)
        self.style_save_button = QPushButton("Save Review Notes", group)
        self.style_ready_button = QPushButton("Mark Ready & Compile", group)
        self.style_draft_button = QPushButton("Return to Draft", group)
        for button in (
            self.style_create_button,
            self.style_refresh_button,
            self.style_save_button,
            self.style_ready_button,
            self.style_draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Style")

        self.style_create_button.clicked.connect(self._style_create)
        self.style_refresh_button.clicked.connect(self._style_refresh)
        self.style_save_button.clicked.connect(self._style_save)
        self.style_ready_button.clicked.connect(self._style_ready)
        self.style_draft_button.clicked.connect(self._style_return_to_draft)
        self._set_style_editor_enabled(False)

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "style_table"):
            return
        self.package_table.setColumnCount(9)
        self.package_table.setHorizontalHeaderLabels(self._headers())
        for row in range(self.package_table.rowCount()):
            shot = self.package_table.item(row, 0)
            source = self.package_table.item(row, 7)
            if source is not None:
                self.package_table.setItem(row, 8, QTableWidgetItem(source.text()))
            if shot is not None:
                self.package_table.setItem(row, 7, QTableWidgetItem(self._style_state(shot.text())))
        self._load_style_draft()

    def _selection_changed(self) -> None:
        super()._selection_changed()
        if hasattr(self, "style_table"):
            self._load_style_draft()

    def _style_state(self, shot_id: str) -> str:
        draft = self.style_compiler.draft(shot_id)
        if draft is None:
            return "Not started"
        if draft.status is StyleCompilationStatus.READY and self.style_compiler.is_current(draft):
            return "Ready / Compiled"
        if not self.style_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

    def _load_style_draft(self) -> None:
        if not hasattr(self, "style_table") or self._selected_shot_id is None:
            return
        draft = self.style_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.style_status.setText(
                "No Style Compiler Draft exists yet. Create one from current governed production state."
            )
            self.style_table.setRowCount(0)
            self.style_notes.clear()
            self.style_create_button.setEnabled(True)
            self.style_refresh_button.setEnabled(False)
            self.style_save_button.setEnabled(False)
            self.style_ready_button.setEnabled(False)
            self.style_draft_button.setEnabled(False)
            self.style_notes.setReadOnly(True)
            return

        self._populate_style_table(draft.style_value())
        self.style_notes.setPlainText(draft.production_notes)
        stale = not self.style_compiler.is_current(draft)
        ready = draft.status is StyleCompilationStatus.READY
        missing = self.style_compiler.missing_prerequisites(draft.shot_id)
        if stale:
            self.style_status.setText(
                "Style compilation is stale because governed production authority changed. Refresh "
                "from the current package to rebuild Style while preserving human review notes."
            )
        elif ready:
            self.style_status.setText(
                "Style authority is Ready and compiled into the current Production Package."
            )
        elif missing:
            self.style_status.setText(
                "Style Draft is current, but final approval is blocked until upstream authority is "
                "Ready: " + ", ".join(missing) + "."
            )
        else:
            self.style_status.setText(
                "Style Draft is current. Review the assembled governed visual language; final "
                "approval remains with the user."
            )
        self.style_create_button.setEnabled(False)
        self.style_refresh_button.setEnabled(stale and not ready)
        self.style_save_button.setEnabled(not stale and not ready)
        self.style_ready_button.setEnabled(not stale and not ready and not missing)
        self.style_draft_button.setEnabled(ready)
        self.style_notes.setReadOnly(stale or ready)

    def _populate_style_table(self, style: dict[str, Any]) -> None:
        fields = (
            "declared_style",
            "declared_tone",
            "camera_language",
            "lighting_language",
            "continuity_language",
            "environment_context",
            "asset_ids",
            "canonical_references",
            "source_policy",
            "provider_neutral",
        )
        self.style_table.setRowCount(len(fields))
        for row, key in enumerate(fields):
            value = style.get(key, "")
            if isinstance(value, list | tuple | dict):
                text = json.dumps(value, sort_keys=True, ensure_ascii=False)
            else:
                text = str(value)
            self.style_table.setItem(row, 0, QTableWidgetItem(key.replace("_", " ").title()))
            self.style_table.setItem(row, 1, QTableWidgetItem(text))

    def _style_create(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_style(lambda: self.style_compiler.create_from_current_package(shot_id))

    def _style_refresh(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_style(lambda: self.style_compiler.rebase_to_current_package(shot_id))

    def _style_save(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_style(
            lambda: self.style_compiler.save_notes(shot_id, self.style_notes.toPlainText())
        )

    def _style_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        try:
            self.style_compiler.save_notes(shot_id, self.style_notes.toPlainText())
            self.style_compiler.mark_ready(shot_id)
        except StyleCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Style Compiler", str(exc))
        self.refresh()

    def _style_return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_style(lambda: self.style_compiler.return_to_draft(shot_id))

    def _run_style(self, action: Any) -> None:
        try:
            action()
        except StyleCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Style Compiler", str(exc))
        self.refresh()

    def _set_style_editor_enabled(self, enabled: bool) -> None:
        for button in (
            self.style_create_button,
            self.style_refresh_button,
            self.style_save_button,
            self.style_ready_button,
            self.style_draft_button,
        ):
            button.setEnabled(enabled)
        self.style_notes.setReadOnly(not enabled)
