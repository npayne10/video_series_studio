"""ProductionTask compilation UI extension for Phase 19.6.2."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from vscs.application.production_tasks import (
    ProductionTask,
    ProductionTaskCompilationContext,
    ProductionTaskCompilationError,
    ProductionTaskCompilerService,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionStatus,
)


def install_production_task_compiler_workspace(workspace_class: type[Any]) -> None:
    """Extend the Production Planning workspace with governed ProductionTask compilation."""
    if getattr(workspace_class, "_production_task_compiler_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_refresh = workspace_type.refresh
    original_selection_changed = workspace_type._selection_changed

    def production_task_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.production_task_compiler = ProductionTaskCompilerService(
            self.universal_compiler,
            self.packages,
        )
        self._compiled_production_tasks: dict[str, tuple[ProductionTask, ...]] = {}
        self._build_production_tasks_tab()
        self._refresh_production_tasks()

    def _build_production_tasks_tab(self: Any) -> None:
        tab = QWidget(self.compiler_tabs)
        tab.setObjectName("production_tasks_tab")
        layout = QVBoxLayout(tab)

        group = QGroupBox("ProductionTask Compilation", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Compile the selected Shot's current approved Universal Production Description into "
            "provider-neutral ProductionTask authority. Phase 19.6.2 creates PLANNED tasks only; "
            "scheduling, provider selection, workflow selection and execution remain downstream.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)

        self.production_task_status = QLabel("", group)
        self.production_task_status.setObjectName("production_task_status_label")
        self.production_task_status.setWordWrap(True)
        group_layout.addWidget(self.production_task_status)

        context_group = QGroupBox("Governed compilation context", group)
        context_form = QFormLayout(context_group)
        self.production_task_production_id = QLineEdit(context_group)
        self.production_task_production_id.setObjectName("production_task_production_id")
        self.production_task_episode_id = QLineEdit(context_group)
        self.production_task_episode_id.setObjectName("production_task_episode_id")
        self.production_task_scene_id = QLineEdit(context_group)
        self.production_task_scene_id.setObjectName("production_task_scene_id")
        self.production_task_approved_by = QLineEdit(context_group)
        self.production_task_approved_by.setObjectName("production_task_approved_by")
        self.production_task_authority_revision = QSpinBox(context_group)
        self.production_task_authority_revision.setObjectName("production_task_authority_revision")
        self.production_task_authority_revision.setMinimum(1)
        self.production_task_authority_revision.setMaximum(999999)
        self.production_task_authority_revision.setValue(1)
        context_form.addRow("Production ID", self.production_task_production_id)
        context_form.addRow("Episode ID", self.production_task_episode_id)
        context_form.addRow("Scene ID (optional)", self.production_task_scene_id)
        context_form.addRow("Approved by", self.production_task_approved_by)
        context_form.addRow("UPD authority revision", self.production_task_authority_revision)
        group_layout.addWidget(context_group)

        actions = QHBoxLayout()
        self.compile_production_tasks_button = QPushButton("Compile Production Tasks", group)
        self.compile_production_tasks_button.setObjectName("compile_production_tasks_button")
        actions.addWidget(self.compile_production_tasks_button)
        actions.addStretch(1)
        group_layout.addLayout(actions)

        self.production_task_table = QTableWidget(0, 9, group)
        self.production_task_table.setObjectName("production_task_table")
        self.production_task_table.setHorizontalHeaderLabels(
            (
                "Task ID",
                "Type",
                "State",
                "Authority Revision",
                "Approved By",
                "Capabilities",
                "Required Inputs",
                "Expected Outputs",
                "Authority Fingerprint",
            )
        )
        self.production_task_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.production_task_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.production_task_table.setAlternatingRowColors(True)
        self.production_task_table.horizontalHeader().setStretchLastSection(True)
        group_layout.addWidget(self.production_task_table, 1)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Production Tasks")

        for editor in (
            self.production_task_production_id,
            self.production_task_episode_id,
            self.production_task_scene_id,
            self.production_task_approved_by,
        ):
            editor.textChanged.connect(self._refresh_production_task_eligibility)
        self.production_task_authority_revision.valueChanged.connect(
            self._refresh_production_task_eligibility
        )
        self.compile_production_tasks_button.clicked.connect(self._compile_production_tasks)

    def _production_task_shot_id(self: Any) -> str:
        return str(self._selected_shot_id or "").strip().upper()

    def _production_task_context(self: Any) -> ProductionTaskCompilationContext:
        return ProductionTaskCompilationContext(
            production_id=self.production_task_production_id.text().strip(),
            episode_id=self.production_task_episode_id.text().strip(),
            scene_id=self.production_task_scene_id.text().strip() or None,
            approved_by=self.production_task_approved_by.text().strip(),
            authority_revision=self.production_task_authority_revision.value(),
        )

    def _production_task_blocker(self: Any) -> str:
        shot_id = self._production_task_shot_id()
        if not shot_id:
            return "Select a Shot before compiling ProductionTasks."
        draft = self.universal_compiler.draft(shot_id)
        if draft is None:
            return "No Universal Production Description exists for the selected Shot."
        if draft.status is not UniversalProductionDescriptionStatus.READY:
            return (
                "Universal Production Description must be Ready before ProductionTask compilation."
            )
        if not self.universal_compiler.is_current(draft):
            return "Universal Production Description is stale against current production authority."
        package = self.packages.current_package(shot_id)
        if package is None:
            return "No current Production Package exists for the selected Shot."
        if package.validation.get("universal_description_complete") is not True:
            return (
                "Universal Production Description authority is not compiled in the current package."
            )
        if package.validation.get("cross_authority_consistent") is not True:
            return "Universal Production Description has unresolved cross-authority consistency."
        if not self.production_task_production_id.text().strip():
            return "Enter the governed Production ID."
        if not self.production_task_episode_id.text().strip():
            return "Enter the governed Episode ID."
        if not self.production_task_approved_by.text().strip():
            return "Enter the human approver identity recorded for the UPD authority."
        return ""

    def _refresh_production_task_eligibility(self: Any, *_args: Any) -> None:
        blocker = self._production_task_blocker()
        self.compile_production_tasks_button.setEnabled(not blocker)
        if blocker:
            self.production_task_status.setText(blocker)
            return
        shot_id = self._production_task_shot_id()
        tasks = self._compiled_production_tasks.get(shot_id, ())
        if tasks:
            self.production_task_status.setText(
                f"{len(tasks)} ProductionTask(s) compiled for {shot_id}. Recompilation is deterministic "
                "for the same governed authority and context revision."
            )
        else:
            self.production_task_status.setText(
                "Ready to compile provider-neutral ProductionTasks. No execution will be submitted."
            )

    def _compile_production_tasks(self: Any) -> None:
        blocker = self._production_task_blocker()
        if blocker:
            self.production_task_status.setText(blocker)
            return
        shot_id = self._production_task_shot_id()
        try:
            tasks = self.production_task_compiler.compile_shot(
                shot_id,
                self._production_task_context(),
            )
        except (ProductionTaskCompilationError, ValueError) as exc:
            self.production_task_status.setText(str(exc))
            QMessageBox.warning(self, "ProductionTask Compilation", str(exc))
            return
        self._compiled_production_tasks[shot_id] = tasks
        self._render_production_tasks(tasks)
        self._refresh_production_task_eligibility()

    def _render_production_tasks(self: Any, tasks: tuple[ProductionTask, ...]) -> None:
        self.production_task_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = (
                task.task_id,
                task.task_type.value,
                task.state.value,
                str(task.authority.revision),
                task.authority.approved_by or "",
                ", ".join(item.value for item in task.capabilities),
                "\n".join(task.required_inputs),
                "\n".join(task.expected_outputs),
                task.authority.fingerprint,
            )
            for column, value in enumerate(values):
                self.production_task_table.setItem(row, column, QTableWidgetItem(value))
        self.production_task_table.resizeColumnsToContents()

    def _refresh_production_tasks(self: Any) -> None:
        if not hasattr(self, "production_task_table"):
            return
        shot_id = self._production_task_shot_id()
        self._render_production_tasks(self._compiled_production_tasks.get(shot_id, ()))
        self._refresh_production_task_eligibility()

    def production_task_refresh(self: Any) -> None:
        original_refresh(self)
        self._refresh_production_tasks()

    def production_task_selection_changed(self: Any) -> None:
        original_selection_changed(self)
        self._refresh_production_tasks()

    workspace_type.__init__ = production_task_init
    workspace_type._build_production_tasks_tab = _build_production_tasks_tab
    workspace_type._production_task_shot_id = _production_task_shot_id
    workspace_type._production_task_context = _production_task_context
    workspace_type._production_task_blocker = _production_task_blocker
    workspace_type._refresh_production_task_eligibility = _refresh_production_task_eligibility
    workspace_type._compile_production_tasks = _compile_production_tasks
    workspace_type._render_production_tasks = _render_production_tasks
    workspace_type._refresh_production_tasks = _refresh_production_tasks
    workspace_type.refresh = production_task_refresh
    workspace_type._selection_changed = production_task_selection_changed
    workspace_type._production_task_compiler_workspace_installed = True
