"""Camera Compiler extension for the Phase 19.4 Production Planning workspace."""

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
from vscs.application.camera_compiler import (
    CameraCompilationStatus,
    CameraCompilerError,
    CameraCompilerService,
)
from vscs.application.production_package import ProductionPackageService
from vscs.application.projects import ProjectService

from .production_package_workspace import ProductionPackageWorkspace


class CameraCompilerWorkspace(ProductionPackageWorkspace):
    """Extend Production Planning with governed Phase 19.4.4 Camera compilation."""

    def __init__(
        self,
        projects: ProjectService,
        packages: ProductionPackageService,
        action_performance: ActionPerformanceCompilerService,
        asset_compiler: AssetCompilerService,
        camera_compiler: CameraCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        self.camera_compiler = camera_compiler
        super().__init__(projects, packages, action_performance, asset_compiler, parent)
        self.package_table.setColumnCount(6)
        self.package_table.setHorizontalHeaderLabels(
            ("Shot", "Production Package", "Action", "Assets", "Camera", "Source")
        )
        self._build_camera_tab()
        self.refresh()

    def _build_camera_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Camera Compiler", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Review the governed Camera Plan before compiling it into production Camera authority. "
            "The governed plan is preserved; provider/model-specific syntax is generated later.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)

        self.camera_status = QLabel("", group)
        self.camera_status.setWordWrap(True)
        group_layout.addWidget(self.camera_status)

        self.camera_table = QTableWidget(0, 2, group)
        self.camera_table.setHorizontalHeaderLabels(("Camera field", "Governed value"))
        self.camera_table.horizontalHeader().setStretchLastSection(True)
        self.camera_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.camera_table, 1)

        group_layout.addWidget(QLabel("Production review notes", group))
        self.camera_notes = QTextEdit(group)
        self.camera_notes.setMaximumHeight(90)
        self.camera_notes.setPlaceholderText(
            "Optional user review notes. Final Camera approval remains with the user."
        )
        group_layout.addWidget(self.camera_notes)

        actions = QHBoxLayout()
        self.camera_create_button = QPushButton("Create from Package", group)
        self.camera_refresh_button = QPushButton("Refresh from Current Package", group)
        self.camera_save_button = QPushButton("Save Review Notes", group)
        self.camera_ready_button = QPushButton("Mark Ready & Compile", group)
        self.camera_draft_button = QPushButton("Return to Draft", group)
        for button in (
            self.camera_create_button,
            self.camera_refresh_button,
            self.camera_save_button,
            self.camera_ready_button,
            self.camera_draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Camera")

        self.camera_create_button.clicked.connect(self._camera_create)
        self.camera_refresh_button.clicked.connect(self._camera_refresh)
        self.camera_save_button.clicked.connect(self._camera_save)
        self.camera_ready_button.clicked.connect(self._camera_ready)
        self.camera_draft_button.clicked.connect(self._camera_return_to_draft)
        self._set_camera_editor_enabled(False)

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "camera_table"):
            return
        self.package_table.setColumnCount(6)
        self.package_table.setHorizontalHeaderLabels(
            ("Shot", "Production Package", "Action", "Assets", "Camera", "Source")
        )
        for row in range(self.package_table.rowCount()):
            shot = self.package_table.item(row, 0)
            source = self.package_table.item(row, 4)
            if source is not None:
                self.package_table.setItem(row, 5, QTableWidgetItem(source.text()))
            if shot is not None:
                self.package_table.setItem(
                    row, 4, QTableWidgetItem(self._camera_state(shot.text()))
                )
        self._load_camera_draft()

    def _selection_changed(self) -> None:
        super()._selection_changed()
        if hasattr(self, "camera_table"):
            self._load_camera_draft()

    def _camera_state(self, shot_id: str) -> str:
        draft = self.camera_compiler.draft(shot_id)
        if draft is None:
            return "Not started"
        if draft.status is CameraCompilationStatus.READY and self.camera_compiler.is_current(draft):
            return "Ready / Compiled"
        if not self.camera_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

    def _load_camera_draft(self) -> None:
        if not hasattr(self, "camera_table") or self._selected_shot_id is None:
            return
        draft = self.camera_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.camera_status.setText(
                "No Camera Compiler Draft exists yet. Create one from the current Production Package."
            )
            self.camera_table.setRowCount(0)
            self.camera_notes.clear()
            self.camera_create_button.setEnabled(True)
            self.camera_refresh_button.setEnabled(False)
            self.camera_save_button.setEnabled(False)
            self.camera_ready_button.setEnabled(False)
            self.camera_draft_button.setEnabled(False)
            self.camera_notes.setReadOnly(True)
            return

        self._populate_camera_table(draft.camera)
        self.camera_notes.setPlainText(draft.production_notes)
        stale = not self.camera_compiler.is_current(draft)
        ready = draft.status is CameraCompilationStatus.READY
        if stale:
            self.camera_status.setText(
                "Camera compilation is stale because its approved Planning source changed. "
                "Refresh from Current Package to load the governed Camera Plan while preserving "
                "human review notes."
            )
        elif ready:
            self.camera_status.setText(
                "Camera authority is Ready and compiled into the current Production Package."
            )
        else:
            self.camera_status.setText(
                "Camera Compiler Draft is current. Review the governed Camera Plan and mark it "
                "Ready when you approve it."
            )
        self.camera_create_button.setEnabled(False)
        self.camera_refresh_button.setEnabled(stale and not ready)
        self.camera_save_button.setEnabled(not stale and not ready)
        self.camera_ready_button.setEnabled(not stale and not ready)
        self.camera_draft_button.setEnabled(ready)
        self.camera_notes.setReadOnly(stale or ready)

    def _populate_camera_table(self, camera: dict[str, Any]) -> None:
        fields = (
            "shot_size",
            "angle",
            "movement",
            "lens_family",
            "focal_length_mm",
            "camera_height_m",
            "screen_direction",
            "composition",
            "focus_strategy",
            "movement_notes",
            "continuity_notes",
            "camera_constraints",
            "camera_profile_asset_id",
        )
        self.camera_table.setRowCount(len(fields))
        for row, key in enumerate(fields):
            value = camera.get(key, "")
            if isinstance(value, list | tuple):
                text = "; ".join(str(item) for item in value)
            else:
                text = str(value)
            self.camera_table.setItem(row, 0, QTableWidgetItem(key.replace("_", " ").title()))
            self.camera_table.setItem(row, 1, QTableWidgetItem(text))

    def _camera_create(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_camera(lambda: self.camera_compiler.create_from_current_package(shot_id))

    def _camera_refresh(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_camera(lambda: self.camera_compiler.rebase_to_current_package(shot_id))

    def _camera_save(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_camera(
            lambda: self.camera_compiler.save_notes(shot_id, self.camera_notes.toPlainText())
        )

    def _camera_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        try:
            self.camera_compiler.save_notes(shot_id, self.camera_notes.toPlainText())
            self.camera_compiler.mark_ready(shot_id)
        except CameraCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Camera Compiler", str(exc))
        self.refresh()

    def _camera_return_to_draft(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        self._run_camera(lambda: self.camera_compiler.return_to_draft(shot_id))

    def _run_camera(self, action: Any) -> None:
        try:
            action()
        except CameraCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(self, "Camera Compiler", str(exc))
        self.refresh()

    def _set_camera_editor_enabled(self, enabled: bool) -> None:
        for button in (
            self.camera_create_button,
            self.camera_refresh_button,
            self.camera_save_button,
            self.camera_ready_button,
            self.camera_draft_button,
        ):
            button.setEnabled(enabled)
        self.camera_notes.setReadOnly(not enabled)
