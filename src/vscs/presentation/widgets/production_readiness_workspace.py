"""Production Readiness Integration UI for Phase 19.6.12."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtWidgets import QGroupBox, QLabel, QTextEdit, QVBoxLayout

from vscs.application.production_tasks import ProductionReadinessAssessment


def install_production_readiness_workspace(workspace_class: type[Any]) -> None:
    """Add read-only integrated production readiness to the Scheduling workspace."""
    if getattr(workspace_class, "_production_readiness_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_refresh = workspace_type._refresh_production_scheduling

    def readiness_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        status = getattr(self, "production_scheduling_status", None)
        if status is None:
            return
        content = status.parentWidget()
        layout = content.layout() if content is not None else None
        if not isinstance(layout, QVBoxLayout):
            return

        group = QGroupBox("Production Readiness", content)
        group.setObjectName("production_readiness_group")
        group_layout = QVBoxLayout(group)
        self.production_readiness_status = QLabel("", group)
        self.production_readiness_status.setObjectName("production_readiness_status")
        self.production_readiness_status.setWordWrap(True)
        group_layout.addWidget(self.production_readiness_status)
        self.production_readiness_findings = QTextEdit(group)
        self.production_readiness_findings.setObjectName("production_readiness_findings")
        self.production_readiness_findings.setReadOnly(True)
        self.production_readiness_findings.setMinimumHeight(90)
        self.production_readiness_findings.setMaximumHeight(150)
        group_layout.addWidget(self.production_readiness_findings)

        status_index = layout.indexOf(status)
        layout.insertWidget(status_index + 1, group)
        self._refresh_production_readiness()

    def _refresh_production_readiness(self: Any) -> None:
        if not hasattr(self, "production_readiness_status"):
            return
        production_id = self._scheduling_production_id()
        if not production_id or not self.projects.is_project_open:
            self.production_readiness_status.setText("Production readiness: not available")
            self.production_readiness_findings.setPlainText(
                "Open a project and select a governed production scope."
            )
            return
        try:
            assessment = cast(
                ProductionReadinessAssessment,
                self.production_scheduling.production_readiness(production_id),
            )
        except (ValueError, RuntimeError) as exc:
            self.production_readiness_status.setText("Production readiness: unavailable")
            self.production_readiness_findings.setPlainText(str(exc))
            return

        self.production_readiness_status.setText(
            f"Production readiness: {assessment.status.value.upper()} — "
            f"tasks {assessment.task_count}, scheduled {assessment.scheduled_count}, "
            f"queue {assessment.queue_entry_count}, executable {assessment.executable_entry_count}."
        )
        lines = [
            f"[{finding.severity.value.upper()}] {finding.code.value}: {finding.message}"
            for finding in assessment.findings
        ]
        self.production_readiness_findings.setPlainText("\n".join(lines))

    def readiness_refresh(self: Any, *_args: Any) -> None:
        original_refresh(self, *_args)
        self._refresh_production_readiness()

    workspace_type.__init__ = readiness_init
    workspace_type._refresh_production_readiness = _refresh_production_readiness
    workspace_type._refresh_production_scheduling = readiness_refresh
    workspace_type._production_readiness_workspace_installed = True
