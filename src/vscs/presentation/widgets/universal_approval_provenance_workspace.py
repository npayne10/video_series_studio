"""UI integration for governed Universal Production Description approval provenance."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
    UniversalProductionDescriptionStatus,
)


def install_universal_approval_provenance_workspace(workspace_class: type[Any]) -> None:
    """Expose approval capture and legacy READY-UPD provenance establishment."""
    if getattr(workspace_class, "_universal_approval_provenance_workspace_installed", False):
        return

    workspace_type: Any = workspace_class
    original_init = workspace_type.__init__
    original_load_universal_draft = workspace_type._load_universal_draft

    def approval_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        group = self.universal_notes.parentWidget()
        group_layout = group.layout()
        if not isinstance(group_layout, QVBoxLayout):
            return

        self.universal_approval_row = QHBoxLayout()
        self.universal_approval_row.addWidget(QLabel("Approved by", group))
        self.universal_approved_by = QLineEdit(group)
        self.universal_approved_by.setObjectName("universal_approved_by")
        self.universal_approved_by.setPlaceholderText(
            "Reviewer/operator approving this exact READY UPD authority"
        )
        self.universal_approval_row.addWidget(self.universal_approved_by, 1)
        self.universal_establish_approval_button = QPushButton(
            "Establish Approval Provenance",
            group,
        )
        self.universal_establish_approval_button.setObjectName(
            "universal_establish_approval_button"
        )
        self.universal_approval_row.addWidget(self.universal_establish_approval_button)

        insert_index = max(0, group_layout.count() - 1)
        group_layout.insertLayout(insert_index, self.universal_approval_row)
        self.universal_establish_approval_button.clicked.connect(
            self._universal_establish_approval_provenance
        )
        self._load_universal_draft()

    def _project_author_default(self: Any) -> str:
        project = getattr(getattr(self, "projects", None), "current_project", None)
        return str(getattr(project, "author", "") or "").strip() if project is not None else ""

    def approval_load_universal_draft(self: Any) -> None:
        original_load_universal_draft(self)
        if not hasattr(self, "universal_approved_by"):
            return
        if self._selected_shot_id is None:
            self.universal_approved_by.clear()
            self.universal_approved_by.setReadOnly(True)
            self.universal_establish_approval_button.setEnabled(False)
            return

        draft = self.universal_compiler.draft(self._selected_shot_id)
        if draft is None:
            self.universal_approved_by.setText(self._project_author_default())
            self.universal_approved_by.setReadOnly(False)
            self.universal_establish_approval_button.setEnabled(False)
            return

        ready = draft.status is UniversalProductionDescriptionStatus.READY
        approval = self.universal_compiler.approval_provenance(draft.shot_id)
        if approval is not None:
            self.universal_approved_by.setText(approval.approved_by)
            self.universal_approved_by.setReadOnly(True)
            self.universal_establish_approval_button.setEnabled(False)
            if ready:
                self.universal_status.setText(
                    self.universal_status.text()
                    + f" Approved by {approval.approved_by} at {approval.approved_at}."
                )
            return

        if not self.universal_approved_by.text().strip():
            self.universal_approved_by.setText(self._project_author_default())
        self.universal_approved_by.setReadOnly(False)
        self.universal_establish_approval_button.setEnabled(
            ready and self.universal_compiler.is_current(draft)
        )
        if ready:
            self.universal_status.setText(
                self.universal_status.text()
                + " This legacy READY UPD has no persisted approval provenance. Enter the approver "
                "and click Establish Approval Provenance before downstream ProductionTask compilation."
            )

    def _universal_ready_with_approval(self: Any) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        reviewer = self.universal_approved_by.text().strip()
        try:
            self.universal_compiler.save_notes(shot_id, self.universal_notes.toPlainText())
            self.universal_compiler.mark_ready_with_approval(shot_id, reviewer)
        except UniversalProductionDescriptionCompilerError as exc:
            QMessageBox.warning(self, "Universal Production Description Compiler", str(exc))
        self.refresh()

    def _universal_establish_approval_provenance(self: Any) -> None:
        if self._selected_shot_id is None:
            return
        shot_id = self._selected_shot_id
        reviewer = self.universal_approved_by.text().strip()
        try:
            approval = self.universal_compiler.establish_approval_provenance(
                shot_id,
                reviewer,
            )
        except UniversalProductionDescriptionCompilerError as exc:
            QMessageBox.warning(self, "UPD Approval Provenance", str(exc))
            return
        QMessageBox.information(
            self,
            "UPD Approval Provenance",
            f"Approval provenance established for {approval.shot_id}.\n\n"
            f"Approved by: {approval.approved_by}\n"
            f"Approved at: {approval.approved_at}\n\n"
            "The approval is bound to the reviewed UPD authority and will survive governed "
            "reference-only refreshes.",
        )
        self.refresh()

    workspace_type.__init__ = approval_init
    workspace_type._project_author_default = _project_author_default
    workspace_type._load_universal_draft = approval_load_universal_draft
    workspace_type._universal_ready = _universal_ready_with_approval
    workspace_type._universal_establish_approval_provenance = (
        _universal_establish_approval_provenance
    )
    workspace_type._universal_approval_provenance_workspace_installed = True
