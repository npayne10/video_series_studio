"""Universal Description and Provider Compiler workspace for Phase 19.4."""

from __future__ import annotations

import json
from typing import Any

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
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
from vscs.application.provider_compiler import (
    ProviderCompilationStatus,
    ProviderCompilerError,
    ProviderCompilerFrameworkService,
)
from vscs.application.style_compiler import StyleCompilerService
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionCompilerService,
    UniversalProductionDescriptionStatus,
)

from .style_compiler_workspace import StyleCompilerWorkspace


class UniversalProductionDescriptionCompilerWorkspace(StyleCompilerWorkspace):
    """Extend Production Planning through Universal and Provider compilation."""

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
        universal_compiler: UniversalProductionDescriptionCompilerService,
        parent: QWidget | None = None,
    ) -> None:
        self.universal_compiler = universal_compiler
        self.provider_compiler = ProviderCompilerFrameworkService(projects, packages)
        super().__init__(
            projects,
            packages,
            action_performance,
            asset_compiler,
            camera_compiler,
            lighting_compiler,
            continuity_compiler,
            style_compiler,
            parent,
        )
        self.package_table.setColumnCount(11)
        self.package_table.setHorizontalHeaderLabels(self._headers())
        self._build_universal_tab()
        self._build_provider_tab()
        self._update_future_footer()
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
            "Universal",
            "Provider",
            "Source",
        )

    def _update_future_footer(self) -> None:
        for label in self.findChildren(QLabel):
            if label.text().startswith("Later Phase 19.4 compilers will add"):
                label.setText(
                    "Later Phase 19.4 work will add final Production Package Validation to this same workspace."
                )
                label.setWordWrap(True)

    def _build_universal_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Universal Production Description Compiler", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Assemble all approved Shot production authority into one canonical provider-neutral "
            "description. This is the source for later provider-specific prompt/output compilation "
            "and does not add new creative intent.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)
        self.universal_status = QLabel("", group)
        self.universal_status.setWordWrap(True)
        group_layout.addWidget(self.universal_status)
        group_layout.addWidget(QLabel("Universal production description", group))
        self.universal_preview = QTextEdit(group)
        self.universal_preview.setReadOnly(True)
        group_layout.addWidget(self.universal_preview, 1)
        group_layout.addWidget(QLabel("Production review notes", group))
        self.universal_notes = QTextEdit(group)
        self.universal_notes.setMaximumHeight(90)
        self.universal_notes.setPlaceholderText(
            "Optional user review notes. Final Universal Production Description approval remains with the user."
        )
        group_layout.addWidget(self.universal_notes)
        actions = QHBoxLayout()
        self.universal_create_button = QPushButton("Assemble from Governed Authority", group)
        self.universal_refresh_button = QPushButton("Refresh from Current Package", group)
        self.universal_save_button = QPushButton("Save Review Notes", group)
        self.universal_ready_button = QPushButton("Mark Ready & Compile", group)
        self.universal_draft_button = QPushButton("Return to Draft", group)
        for button in (
            self.universal_create_button,
            self.universal_refresh_button,
            self.universal_save_button,
            self.universal_ready_button,
            self.universal_draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Universal Description")
        self.universal_create_button.clicked.connect(self._universal_create)
        self.universal_refresh_button.clicked.connect(self._universal_refresh)
        self.universal_save_button.clicked.connect(self._universal_save)
        self.universal_ready_button.clicked.connect(self._universal_ready)
        self.universal_draft_button.clicked.connect(self._universal_return_to_draft)

    def _build_provider_tab(self) -> None:
        tab = QWidget(self.compiler_tabs)
        layout = QVBoxLayout(tab)
        group = QGroupBox("Provider Compiler Framework", tab)
        group_layout = QVBoxLayout(group)
        guidance = QLabel(
            "Translate the approved Universal Production Description into a deterministic provider contract. "
            "This phase compiles provider output only; it does not submit ComfyUI jobs or choose a workflow automatically.",
            group,
        )
        guidance.setWordWrap(True)
        group_layout.addWidget(guidance)
        provider_row = QHBoxLayout()
        provider_row.addWidget(QLabel("Provider", group))
        self.provider_selector = QComboBox(group)
        for descriptor in self.provider_compiler.providers():
            self.provider_selector.addItem(descriptor.display_name, descriptor.provider_id)
        provider_row.addWidget(self.provider_selector)
        provider_row.addStretch(1)
        group_layout.addLayout(provider_row)
        self.provider_status = QLabel("", group)
        self.provider_status.setWordWrap(True)
        group_layout.addWidget(self.provider_status)
        group_layout.addWidget(QLabel("Compiled provider output", group))
        self.provider_preview = QTextEdit(group)
        self.provider_preview.setReadOnly(True)
        group_layout.addWidget(self.provider_preview, 1)
        group_layout.addWidget(QLabel("Production review notes", group))
        self.provider_notes = QTextEdit(group)
        self.provider_notes.setMaximumHeight(90)
        self.provider_notes.setPlaceholderText(
            "Optional review notes. Final provider-output approval remains with the user."
        )
        group_layout.addWidget(self.provider_notes)
        actions = QHBoxLayout()
        self.provider_create_button = QPushButton("Compile Provider Draft", group)
        self.provider_refresh_button = QPushButton("Refresh from Universal", group)
        self.provider_save_button = QPushButton("Save Review Notes", group)
        self.provider_ready_button = QPushButton("Mark Ready & Compile", group)
        self.provider_draft_button = QPushButton("Return to Draft", group)
        for button in (
            self.provider_create_button,
            self.provider_refresh_button,
            self.provider_save_button,
            self.provider_ready_button,
            self.provider_draft_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        group_layout.addLayout(actions)
        layout.addWidget(group, 1)
        self.compiler_tabs.addTab(tab, "Provider Output")
        self.provider_selector.currentIndexChanged.connect(self._load_provider_draft)
        self.provider_create_button.clicked.connect(self._provider_create)
        self.provider_refresh_button.clicked.connect(self._provider_refresh)
        self.provider_save_button.clicked.connect(self._provider_save)
        self.provider_ready_button.clicked.connect(self._provider_ready)
        self.provider_draft_button.clicked.connect(self._provider_return_to_draft)

    def refresh(self) -> None:
        super().refresh()
        if not hasattr(self, "universal_preview"):
            return
        self.package_table.setColumnCount(11)
        self.package_table.setHorizontalHeaderLabels(self._headers())
        for row in range(self.package_table.rowCount()):
            shot = self.package_table.item(row, 0)
            source = self.package_table.item(row, 8)
            if source is not None:
                self.package_table.setItem(row, 10, QTableWidgetItem(source.text()))
            if shot is not None:
                self.package_table.setItem(row, 8, QTableWidgetItem(self._universal_state(shot.text())))
                self.package_table.setItem(row, 9, QTableWidgetItem(self._provider_state(shot.text())))
        self._update_future_footer()
        self._load_universal_draft()
        if hasattr(self, "provider_preview"):
            self._load_provider_draft()

    def _selection_changed(self) -> None:
        super()._selection_changed()
        if hasattr(self, "universal_preview"):
            self._load_universal_draft()
        if hasattr(self, "provider_preview"):
            self._load_provider_draft()

    def _universal_state(self, shot_id: str) -> str:
        draft = self.universal_compiler.draft(shot_id)
        if draft is None:
            return "Not started"
        if draft.status is UniversalProductionDescriptionStatus.READY and self.universal_compiler.is_current(draft):
            return "Ready / Compiled"
        if not self.universal_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        if self.universal_compiler.consistency_findings(shot_id):
            return "Draft / Blocked"
        return draft.status.value.title()

    def _selected_provider(self) -> str:
        value = self.provider_selector.currentData() if hasattr(self, "provider_selector") else None
        return str(value or "comfyui")

    def _provider_state(self, shot_id: str) -> str:
        provider_id = self._selected_provider()
        draft = self.provider_compiler.draft(shot_id, provider_id)
        if draft is None:
            return "Not started"
        if draft.status is ProviderCompilationStatus.READY and self.provider_compiler.is_current(draft):
            return "Ready / Compiled"
        if not self.provider_compiler.is_current(draft):
            return f"{draft.status.value.title()} / Stale"
        return draft.status.value.title()

    def _load_universal_draft(self) -> None:
        if not hasattr(self, "universal_preview") or self._selected_shot_id is None:
            return
        draft = self.universal_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.universal_status.setText(
                "No Universal Production Description Draft exists yet. Assemble one from current governed authority."
            )
            self.universal_preview.clear()
            self.universal_notes.clear()
            self.universal_create_button.setEnabled(True)
            self.universal_refresh_button.setEnabled(False)
            self.universal_save_button.setEnabled(False)
            self.universal_ready_button.setEnabled(False)
            self.universal_draft_button.setEnabled(False)
            self.universal_notes.setReadOnly(True)
            return
        value = draft.description_value()
        self.universal_preview.setPlainText(self._human_readable_description(value))
        self.universal_notes.setPlainText(draft.production_notes)
        stale = not self.universal_compiler.is_current(draft)
        ready = draft.status is UniversalProductionDescriptionStatus.READY
        missing = self.universal_compiler.missing_prerequisites(draft.shot_id)
        findings = self.universal_compiler.consistency_findings(draft.shot_id)
        if stale:
            self.universal_status.setText(
                "Universal Production Description is stale because governed production authority changed. Refresh it before final approval."
            )
        elif ready:
            self.universal_status.setText(
                "Universal Production Description authority is Ready and compiled into the current Production Package."
            )
        elif missing:
            self.universal_status.setText(
                "Universal Production Description Draft is current, but final approval is blocked until upstream authority is Ready: "
                + ", ".join(missing) + "."
            )
        elif findings:
            self.universal_status.setText(
                "Universal Production Description Draft is current, but final approval is blocked by "
                f"{len(findings)} cross-authority consistency finding(s). Correct the governed upstream authority, then refresh this Draft."
            )
        else:
            self.universal_status.setText(
                "Universal Production Description Draft is current. Review the assembled provider-neutral description; final approval remains with the user."
            )
        self.universal_create_button.setEnabled(False)
        self.universal_refresh_button.setEnabled(stale and not ready)
        self.universal_save_button.setEnabled(not stale and not ready)
        self.universal_ready_button.setEnabled(not stale and not ready and not missing and not findings)
        self.universal_draft_button.setEnabled(ready)
        self.universal_notes.setReadOnly(stale or ready)

    def _load_provider_draft(self) -> None:
        if not hasattr(self, "provider_preview") or self._selected_shot_id is None:
            return
        provider_id = self._selected_provider()
        draft = self.provider_compiler.draft(self._selected_shot_id, provider_id)
        package = self.packages.current_package(self._selected_shot_id)
        universal_ready = bool(
            package is not None
            and package.validation.get("universal_description_complete") is True
            and package.validation.get("cross_authority_consistent") is True
        )
        if draft is None:
            self.provider_preview.clear()
            self.provider_notes.clear()
            if universal_ready:
                self.provider_status.setText(
                    "No Provider Draft exists yet. Compile one from the approved Universal Production Description."
                )
            else:
                self.provider_status.setText(
                    "Provider compilation is blocked until the Universal Production Description is approved and cross-authority consistent."
                )
            self.provider_create_button.setEnabled(universal_ready)
            self.provider_refresh_button.setEnabled(False)
            self.provider_save_button.setEnabled(False)
            self.provider_ready_button.setEnabled(False)
            self.provider_draft_button.setEnabled(False)
            self.provider_notes.setReadOnly(True)
            return
        self.provider_preview.setPlainText(json.dumps(draft.output_value(), indent=2, sort_keys=True, ensure_ascii=False))
        self.provider_notes.setPlainText(draft.production_notes)
        stale = not self.provider_compiler.is_current(draft)
        ready = draft.status is ProviderCompilationStatus.READY
        if stale:
            self.provider_status.setText(
                "Provider output is stale because the approved Universal Production Description changed. Refresh before approval."
            )
        elif ready:
            self.provider_status.setText(
                "Provider output is Ready and compiled into the current Production Package. Execution has not been submitted."
            )
        else:
            self.provider_status.setText(
                "Provider Draft is current. Review the provider contract; final approval remains with the user. No provider execution occurs in this phase."
            )
        self.provider_create_button.setEnabled(False)
        self.provider_refresh_button.setEnabled(stale and not ready and universal_ready)
        self.provider_save_button.setEnabled(not stale and not ready)
        self.provider_ready_button.setEnabled(not stale and not ready and universal_ready)
        self.provider_draft_button.setEnabled(ready)
        self.provider_notes.setReadOnly(stale or ready)

    @classmethod
    def _human_readable_description(cls, description: dict[str, Any]) -> str:
        sections: list[str] = []
        section_keys = (
            ("SHOT", "shot"),
            ("ACTION & PERFORMANCE", "action_performance"),
            ("ASSETS", "assets"),
            ("CAMERA", "camera"),
            ("LIGHTING", "lighting"),
            ("ENVIRONMENT", "environment"),
            ("CONTINUITY", "continuity"),
            ("STYLE", "style"),
            ("DIALOGUE", "dialogue"),
            ("EFFECTS", "effects"),
            ("CANONICAL REFERENCES", "canonical_references"),
            ("CONSISTENCY FINDINGS", "consistency_findings"),
        )
        for heading, key in section_keys:
            value = description.get(key)
            if value in (None, "", {}, []):
                continue
            sections.append(heading)
            sections.extend(cls._render_value(value, indent=0))
            sections.append("")
        sections.append("PRODUCTION POLICY")
        sections.append(f"  Source Policy: {cls._display_scalar(description.get('source_policy', ''))}")
        sections.append(f"  Provider Neutral: {cls._display_scalar(description.get('provider_neutral', True))}")
        return "\n".join(sections).rstrip()

    @classmethod
    def _render_value(cls, value: Any, *, indent: int) -> list[str]:
        prefix = "  " * (indent + 1)
        if isinstance(value, dict):
            lines: list[str] = []
            for key, item in value.items():
                label = key.replace("_", " ").title()
                if isinstance(item, dict | list | tuple):
                    if item in ({}, [], ()):
                        continue
                    lines.append(f"{prefix}{label}:")
                    lines.extend(cls._render_value(item, indent=indent + 1))
                elif item not in (None, ""):
                    lines.append(f"{prefix}{label}: {cls._display_scalar(item)}")
            return lines
        if isinstance(value, list | tuple):
            lines = []
            for index, item in enumerate(value, start=1):
                if isinstance(item, dict):
                    lines.append(f"{prefix}{index}.")
                    lines.extend(cls._render_value(item, indent=indent + 1))
                else:
                    lines.append(f"{prefix}- {cls._display_scalar(item)}")
            return lines
        return [f"{prefix}{cls._display_scalar(value)}"]

    @staticmethod
    def _display_scalar(value: Any) -> str:
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, float):
            return f"{value:g}"
        if isinstance(value, str):
            return value.replace("\\n", "\n")
        return str(value)

    def _universal_create(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            self._run_universal(lambda: self.universal_compiler.create_from_current_package(shot_id))

    def _universal_refresh(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            self._run_universal(lambda: self.universal_compiler.rebase_to_current_package(shot_id))

    def _universal_save(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            self._run_universal(lambda: self.universal_compiler.save_notes(shot_id, self.universal_notes.toPlainText()))

    def _universal_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        try:
            self.universal_compiler.save_notes(shot_id, self.universal_notes.toPlainText())
            self.universal_compiler.mark_ready(shot_id)
        except UniversalProductionDescriptionCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Universal Production Description Compiler", str(exc))
        self.refresh()

    def _universal_return_to_draft(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            self._run_universal(lambda: self.universal_compiler.return_to_draft(shot_id))

    def _run_universal(self, action: Any) -> None:
        try:
            action()
        except UniversalProductionDescriptionCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Universal Production Description Compiler", str(exc))
        self.refresh()

    def _provider_create(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            provider_id = self._selected_provider()
            self._run_provider(lambda: self.provider_compiler.create_from_current_package(shot_id, provider_id))

    def _provider_refresh(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            provider_id = self._selected_provider()
            self._run_provider(lambda: self.provider_compiler.rebase_to_current_package(shot_id, provider_id))

    def _provider_save(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            provider_id = self._selected_provider()
            self._run_provider(lambda: self.provider_compiler.save_notes(shot_id, provider_id, self.provider_notes.toPlainText()))

    def _provider_ready(self) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        provider_id = self._selected_provider()
        try:
            self.provider_compiler.save_notes(shot_id, provider_id, self.provider_notes.toPlainText())
            self.provider_compiler.mark_ready(shot_id, provider_id)
        except ProviderCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Provider Compiler Framework", str(exc))
        self.refresh()

    def _provider_return_to_draft(self) -> None:
        if self._selected_shot_id is not None:
            shot_id = self._selected_shot_id
            provider_id = self._selected_provider()
            self._run_provider(lambda: self.provider_compiler.return_to_draft(shot_id, provider_id))

    def _run_provider(self, action: Any) -> None:
        try:
            action()
        except ProviderCompilerError as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Provider Compiler Framework", str(exc))
        self.refresh()
