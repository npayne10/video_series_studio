"""ProductionTask compilation UI extension for Phase 19.6.2."""

from __future__ import annotations

import re
from collections.abc import Iterable
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

_SHOT_HIERARCHY_PATTERN = re.compile(
    r"^(?P<episode>EP-[A-Z0-9]+)-(?P<scene>SCN-[A-Z0-9]+)-(?P<shot>SHT-[A-Z0-9]+)$",
    flags=re.IGNORECASE,
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
        compiled_production_tasks: dict[str, tuple[ProductionTask, ...]] = {}
        self._compiled_production_tasks = compiled_production_tasks
        self._build_production_tasks_tab()
        self._refresh_production_tasks()
        self._apply_production_planning_refresh_policy()

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
        self.production_task_authority_revision = QLineEdit(context_group)
        self.production_task_authority_revision.setObjectName("production_task_authority_revision")
        for editor in (
            self.production_task_production_id,
            self.production_task_episode_id,
            self.production_task_scene_id,
            self.production_task_approved_by,
            self.production_task_authority_revision,
        ):
            editor.setReadOnly(True)
        context_form.addRow("Production ID", self.production_task_production_id)
        context_form.addRow("Episode ID", self.production_task_episode_id)
        context_form.addRow("Scene ID", self.production_task_scene_id)
        context_form.addRow("Approved by", self.production_task_approved_by)
        context_form.addRow("UPD authority revision", self.production_task_authority_revision)
        group_layout.addWidget(context_group)

        self.production_task_context_source = QLabel("", group)
        self.production_task_context_source.setObjectName("production_task_context_source_label")
        self.production_task_context_source.setWordWrap(True)
        group_layout.addWidget(self.production_task_context_source)

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

        self.compile_production_tasks_button.clicked.connect(self._compile_production_tasks)

    def _production_task_shot_id(self: Any) -> str:
        return str(self._selected_shot_id or "").strip().upper()

    def _production_task_context(self: Any) -> ProductionTaskCompilationContext:
        revision_text = self.production_task_authority_revision.text().strip()
        revision = int(revision_text) if revision_text.isdigit() else 0
        return ProductionTaskCompilationContext(
            production_id=self.production_task_production_id.text().strip(),
            episode_id=self.production_task_episode_id.text().strip(),
            scene_id=self.production_task_scene_id.text().strip() or None,
            approved_by=self.production_task_approved_by.text().strip(),
            authority_revision=revision,
        )

    def _refresh_production_task_context(self: Any) -> None:
        shot_id = self._production_task_shot_id()
        production_id = ""
        episode_id = ""
        scene_id = ""
        approved_by = ""
        revision = 0
        sources: list[str] = []
        legacy_fallbacks: list[str] = []

        package = self.packages.current_package(shot_id) if shot_id else None
        if package is not None:
            package_sources = (
                getattr(package, "production_review", None),
                getattr(package, "universal_description", None),
                getattr(package, "validation", None),
                getattr(package, "story_context", None),
                getattr(package, "shot", None),
            )
            production_id = _first_governed_value(
                package_sources,
                ("production_id", "project_id"),
            )
            episode_id = _first_governed_value(
                package_sources,
                ("episode_id", "episode"),
            )
            scene_id = _first_governed_value(
                package_sources,
                ("scene_id", "scene"),
            )
            approved_by = _first_governed_value(
                package_sources,
                (
                    "production_review_approved_by",
                    "authority_approved_by",
                    "approved_by",
                    "reviewed_by",
                ),
            )
            revision_value = _first_governed_value(
                package_sources,
                ("upd_authority_revision", "authority_revision", "revision"),
            )
            if revision_value.isdigit() and int(revision_value) >= 1:
                revision = int(revision_value)
            if any((production_id, episode_id, scene_id, approved_by, revision)):
                sources.append("current governed Production Package")

        hierarchy = _shot_hierarchy(shot_id)
        if not episode_id and hierarchy is not None:
            episode_id = hierarchy[0]
            sources.append("governed Shot hierarchy")
        if not scene_id and hierarchy is not None:
            scene_id = hierarchy[1]
            if "governed Shot hierarchy" not in sources:
                sources.append("governed Shot hierarchy")

        project = getattr(getattr(self, "projects", None), "current_project", None)
        if not production_id and project is not None:
            production_id = str(getattr(project, "project_id", "") or "").strip()
            if production_id:
                sources.append("project identity")
        if not approved_by and project is not None:
            approved_by = str(getattr(project, "author", "") or "").strip()
            if approved_by:
                legacy_fallbacks.append("approver uses project author")

        if revision < 1:
            revision = 1
            legacy_fallbacks.append("UPD revision defaults to 1")

        self.production_task_production_id.setText(production_id)
        self.production_task_episode_id.setText(episode_id)
        self.production_task_scene_id.setText(scene_id)
        self.production_task_approved_by.setText(approved_by)
        self.production_task_authority_revision.setText(str(revision))

        source_text = "Derived automatically"
        if sources:
            source_text += " from " + ", ".join(dict.fromkeys(sources))
        source_text += "."
        if legacy_fallbacks:
            source_text += " Legacy compatibility: " + "; ".join(legacy_fallbacks) + "."
        self.production_task_context_source.setText(source_text)

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
            return "Governed Production ID is unavailable from the current project or package."
        if not self.production_task_episode_id.text().strip():
            return "Governed Episode ID is unavailable from the current Shot hierarchy or package."
        if not self.production_task_approved_by.text().strip():
            return "UPD approver identity is unavailable from governed authority or project metadata."
        revision = self.production_task_authority_revision.text().strip()
        if not revision.isdigit() or int(revision) < 1:
            return "UPD authority revision is unavailable from governed authority."
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
                "Governed compilation context resolved. Ready to compile provider-neutral "
                "ProductionTasks; no execution will be submitted."
            )

    def _compile_production_tasks(self: Any) -> None:
        self._refresh_production_task_context()
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

    def _apply_production_planning_refresh_policy(self: Any) -> None:
        shot_id = self._production_task_shot_id()
        if not shot_id:
            return
        refresh_bindings = (
            ("action_performance", "refresh_source_button"),
            ("asset_compiler", "asset_refresh_button"),
            ("camera_compiler", "camera_refresh_button"),
            ("lighting_compiler", "lighting_refresh_button"),
            ("continuity_compiler", "continuity_refresh_button"),
            ("style_compiler", "style_refresh_button"),
            ("universal_compiler", "universal_refresh_button"),
        )
        for service_name, button_name in refresh_bindings:
            service = getattr(self, service_name, None)
            button = getattr(self, button_name, None)
            if service is None or button is None:
                continue
            draft = service.draft(shot_id)
            if draft is None:
                continue
            status = getattr(getattr(draft, "status", None), "value", "")
            button.setEnabled(status != "ready")

    def _refresh_production_tasks(self: Any) -> None:
        if not hasattr(self, "production_task_table"):
            return
        self._refresh_production_task_context()
        shot_id = self._production_task_shot_id()
        self._render_production_tasks(self._compiled_production_tasks.get(shot_id, ()))
        self._refresh_production_task_eligibility()

    def production_task_refresh(self: Any) -> None:
        original_refresh(self)
        self._refresh_production_tasks()
        self._apply_production_planning_refresh_policy()

    def production_task_selection_changed(self: Any) -> None:
        original_selection_changed(self)
        self._refresh_production_tasks()
        self._apply_production_planning_refresh_policy()

    workspace_type.__init__ = production_task_init
    workspace_type._build_production_tasks_tab = _build_production_tasks_tab
    workspace_type._production_task_shot_id = _production_task_shot_id
    workspace_type._production_task_context = _production_task_context
    workspace_type._refresh_production_task_context = _refresh_production_task_context
    workspace_type._production_task_blocker = _production_task_blocker
    workspace_type._refresh_production_task_eligibility = _refresh_production_task_eligibility
    workspace_type._compile_production_tasks = _compile_production_tasks
    workspace_type._render_production_tasks = _render_production_tasks
    workspace_type._apply_production_planning_refresh_policy = (
        _apply_production_planning_refresh_policy
    )
    workspace_type._refresh_production_tasks = _refresh_production_tasks
    workspace_type.refresh = production_task_refresh
    workspace_type._selection_changed = production_task_selection_changed
    workspace_type._production_task_compiler_workspace_installed = True


def _first_governed_value(sources: Iterable[Any], keys: tuple[str, ...]) -> str:
    for source in sources:
        value = _nested_governed_value(source, keys)
        if value:
            return value
    return ""


def _nested_governed_value(value: Any, keys: tuple[str, ...]) -> str:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if candidate is not None and not isinstance(candidate, dict | list | tuple):
                text = str(candidate).strip()
                if text:
                    return text
        for nested in value.values():
            found = _nested_governed_value(nested, keys)
            if found:
                return found
    elif isinstance(value, list | tuple):
        for nested in value:
            found = _nested_governed_value(nested, keys)
            if found:
                return found
    return ""


def _shot_hierarchy(shot_id: str) -> tuple[str, str] | None:
    match = _SHOT_HIERARCHY_PATTERN.fullmatch(shot_id.strip())
    if match is None:
        return None
    return match.group("episode").upper(), match.group("scene").upper()
