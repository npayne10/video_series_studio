"""Lighting Compiler extension for the Phase 19.4 Production Planning workspace."""

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
from vscs.application.lighting_compiler import (
    LightingCompilationStatus,
    LightingCompilerError,
    LightingCompilerService,
)
from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService

from .camera_compiler_workspace import CameraCompilerWorkspace


class LightingCompilerWorkspace(CameraCompilerWorkspace):
    """Extend Production Planning with governed Phase 19.4.5 Lighting compilation."""

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        action_performance: ActionPerformanceCompilerService,
        asset_compiler: AssetCompilerService,
        camera_compiler: CameraCompilerService,
        lighting_compiler: LightingCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        self.lighting_compiler = lighting_compiler
        super().__init__(
            projects,
            packages,
            action_performance,
            asset_compiler,
            camera_compiler,
            parent,
        )
        self.package_table.setColumnCount(7)
        self.package_table.setHorizontalHeaderLabels(
            ("Shot", "Production Package", "Action", "Assets", "Camera", "Lighting", "Source")
        )
        self._build_lighting_tab()
        self.refresh()

    def _build_lighting_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Lighting Compiler", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Review the governed Lighting Plan before compiling it into production Lighting "
            "authority. The governed plan is preserved; renderer/model-specific syntax is "
            "generated later.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)

        self.lighting_status = QLabel("", group)
        self.lighting_status.setWordWrap(True)
        group_layout.addWidget(self.lighting_status)

        self.lighting_table = QTableWidget(0, 2, group)
        self.lighting_table.setHorizontalHeaderLabels(("Lighting field", "Governed value"))
        self.lighting_table.horizontalHeader().setStretchLastSection(True)
        self.lighting_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.lighting_table, 1)

        group_layout.addWidget(QLabel("Production review notes", group))
        self.lighting_notes = QTextEdit(group)
        self.lighting_notes.setMaximumHeight(90)
        self.lighting_notes.setPlaceholderText(
            "Optional user review notes. Final Lighting approval remains with the user."
        )
        group_layout.addWidget(self.lighting_notes)

        actions = QHBoxLayout()
        self.lighting_create_button = QPushButton("Create from Package", group)
        self.lighting_refresh_button = QPushButton("Refresh from Current Package", group)
        self.lighting_save_button = QPushButton("Save Review Notes", group)
        self.lighting_ready_button = QPushButton("Mark Ready & Compile", group)
        self.lighting_draft_button = QPushButton("Return to Draft", group)
        for button in (
            self.lighting_create_button,
            self.lighting_refresh_button,
            self.lighting_save_button,
            self.lighting_ready_button,
            self.lighting_draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Lighting")

        self.lighting_create_button.clicked.connect(self._lighting_create)
        self.lighting_refresh_button.clicked.connect(self._lighting_refresh)
        self.lighting_save_button.clicked.connect(self._lighting_save)
        self.lighting_ready_button.clicked.connect(self._lighting_ready)
        self.lighting_draft_button.clicked.connect(self._lighting_return_to_draft)
        self._set_lighting_editor_enabled(False)

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "lighting_table"):
            return
        self.package_table.setColumnCount(7)
        self.package_table.setHorizontalHeaderLabels(
            ("Shot", "Production Package", "Action", "Assets", "Camera", "Lighting", "Source")
        )
        for row in range(self.package_table.rowCount()):
            shot = self.package_table.item(row, 0)
            source = self.package_table.item(row, 5)
            if source is not None:
                self.package_table.setItem(row, 6, QTableWidgetItem(source.text()))
            if shot is not None:
                self.package_table.setItem(
                    row, 5, QTableWidgetItem(self._lighting_state(shot.text()))
                )
        self._load_lighting_draft()

    def _selection_changed(self) -> None:
        super()._selection_changed()
        if hasattr(self, "lighting_table"):
            self._load_lighting_draft()

    def _lighting_state(self, shot_id: str) -> str:
        draft = self.lighting_compiler.draft(shot_id)
        if draft is None:
            return "Not started"
        if draft.status is LightingCompilationStatus.READY and self.lighting_compiler.is_current(
            draft
        ):
            return "Ready / Compiled"
        if not self.lighting_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

    def _load_lighting_draft(self) -> None:
        if not hasattr(self, "lighting_table") or self._selected_shot_id is None:
            return
        draft = self.lighting_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.lighting_status.setText(
                "No Lighting Compiler Draft exists yet. Create one from the current Production "
                "Package."
            )
            self.lighting_table.setRowCount(0)
            self.lighting_notes.clear()
            self.lighting_create_button.setEnabled(True)
            self.lighting_refresh_button.setEnabled(False)
            self.lighting_save_button.setEnabled(False)
            self.lighting_ready_button.setEnabled(False)
            self.lighting_draft_button.setEnabled(False)
            self.lighting_notes.setReadOnly(True)
            return

        self._populate_lighting_table(draft.lighting)
        self.lighting_notes.setPlainText(draft.production_notes)
        stale = not self.lighting_compiler.is_current(draft)
        ready = draft.status is LightingCompilationStatus.READY
        if stale:
            self.lighting_status.setText(
                "Lighting compilation is stale because its approved Planning source changed. "
                "Refresh from Current Package to rebuild the governed Lighting Plan while preserving "
                "human review notes."
            )
        elif ready:
            self.lighting_status.setText(
                "Lighting authority is Ready and compiled into the current Production Package."
            )
        else:
            self.lighting_status.setText(
                "Lighting Compiler Draft is current. Review the governed Lighting Plan, or refresh "
                "it from the current Production Package to rebuild the Draft, then mark it Ready "
                "when you approve it."
            )
        self.lighting_create_button.setEnabled(False)
        self.lighting_refresh_button.setEnabled(not ready)
        self.lighting_save_button.setEnabled(not stale and not ready)
        self.lighting_ready_button.setEnabled(not stale and not ready)
        self.lighting_draft_button.setEnabled(ready)
        self.lighting_notes.setReadOnly(stale or ready)

    def _populate_lighting_table(self, lighting: dict[str, Any]) -> None:
        fields = (
            "lighting_intent",
            "key_direction",
            "key_quality",
            "color_temperature_k",
            "fill_level_percent",
            "exposure_intent",
            "source_strategy",
            "shadow_strategy",
            "subject_readability",
            "separation_strategy",
            "continuity_notes",
            "lighting_constraints",
            "lighting_profile_asset_id",
        )
        self.lighting_table.setRowCount(len(fields))
        for row, key in enumerate(fields):
            value = lighting.get(key, "")
            if isinstance(value, list | tuple):
                text = "; ".join(str(item) for item in value)
            else:
                text = str(value)
            self.lighting_table.setItem(row, 0, QTableWidgetItem(key.replace("_", " ").title()))
            self.lighting_table.setItem(row, 1, QTableWidgetItem(text))

    def _lighting_create(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_lighting(lambda: self.lighting_compiler.create_from_current_package(shot_id))

    def _lighting_refresh(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_lighting(lambda: self.lighting_compiler.rebase_to_current_package(shot_id))

    def _lighting_save(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_lighting(
            lambda: self.lighting_compiler.save_notes(shot_id, self.lighting_notes.toPlainText())
        )

    def _lighting_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        try:
            self.lighting_compiler.save_notes(shot_id, self.lighting_notes.toPlainText())
            self.lighting_compiler.mark_ready(shot_id)
        except LightingCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Lighting Compiler", str(exc))
        self.refresh()

    def _lighting_return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_lighting(lambda: self.lighting_compiler.return_to_draft(shot_id))

    def _run_lighting(self, action: Any) -> None:
        try:
            action()
        except LightingCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Lighting Compiler", str(exc))
        self.refresh()

    def _set_lighting_editor_enabled(self, enabled: bool) -> None:
        for button in (
            self.lighting_create_button,
            self.lighting_refresh_button,
            self.lighting_save_button,
            self.lighting_ready_button,
            self.lighting_draft_button,
        ):
            button.setEnabled(enabled)
        self.lighting_notes.setReadOnly(not enabled)
