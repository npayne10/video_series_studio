"""Phase 19.4.10 Production Package Review workspace integration."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.production_package_acceptance import (
    ProductionPackageAcceptanceService,
)
from vscs.application.production_package_review import (
    ProductionPackageReview,
    ProductionPackageReviewService,
    ReviewStatus,
)


def _provider_id(workspace: Any) -> str:
    selector = getattr(workspace, "provider_selector", None)
    return (
        str(selector.currentData() or "comfyui")
        if selector is not None
        else "comfyui"
    )


def _render(workspace: Any, review: ProductionPackageReview, persisted: bool) -> None:
    lines = [
        f"Shot: {review.shot_id}",
        f"Provider: {review.provider_id}",
        f"Status: {review.status.value}",
        f"Validation: {'PASS' if review.validation_passed else 'FAIL'}",
        f"Assets: {review.asset_count}",
        f"Canonical references: {review.canonical_reference_count}",
        f"Provider contract: {review.provider_contract or 'not available'}",
        f"Provider execution: {review.provider_execution or 'not available'}",
        "",
        "Findings:",
    ]
    lines.extend(
        f"- [{item.severity.upper()}] {item.message}" for item in review.findings
    )
    if not review.findings:
        lines.append("- No blocking validation findings.")
    if persisted:
        lines.extend(
            (
                "",
                f"Reviewed by: {review.reviewed_by or 'not recorded'}",
                f"Reviewed at: {review.reviewed_at}",
                f"Review notes: {review.review_notes or 'none'}",
            )
        )
    workspace.production_review_summary.setPlainText("\n".join(lines))
    workspace.production_review_reviewer.setText(review.reviewed_by)
    workspace.production_review_notes.setPlainText(review.review_notes)

    validation_confirmed = workspace.production_review_service.validation_confirmed(
        review.shot_id,
        review.provider_id,
    )
    if review.status is ReviewStatus.APPROVED:
        status = "APPROVED FOR PRODUCTION — final human approval is current."
    elif review.status is ReviewStatus.STALE:
        status = (
            "STALE — governed authority changed after review. "
            "Revalidate and approve again."
        )
    elif review.status is ReviewStatus.CHANGES_REQUIRED:
        status = (
            "CHANGES REQUIRED — correct upstream authority, recompile, then revalidate."
        )
    elif review.validation_passed and validation_confirmed:
        status = "VALIDATION PASS — ready for final human review and approval."
    elif review.validation_passed:
        status = (
            "READY FOR VALIDATION — click Validate Package before final human approval."
        )
    else:
        status = "VALIDATION FAILED — resolve blocking findings before approval."
    workspace.production_review_status.setText(status)

    acceptance = workspace.production_acceptance_service.assess(
        review.shot_id,
        review.provider_id,
    )
    if acceptance.accepted:
        acceptance_text = (
            "PHASE 19.4 ACCEPTED — this current Production Package has passed final "
            "integration checks and is authorized for later provider execution."
        )
    else:
        failed = [check.message for check in acceptance.checks if not check.passed]
        detail = (
            failed[0]
            if failed
            else "Final integration requirements are incomplete."
        )
        acceptance_text = f"PHASE 19.4 NOT READY — {detail}"
    workspace.production_acceptance_status.setText(acceptance_text)

    workspace.production_review_approve_button.setEnabled(
        review.validation_passed
        and validation_confirmed
        and review.status is not ReviewStatus.APPROVED
    )
    workspace.production_review_changes_button.setEnabled(
        review.status is not ReviewStatus.APPROVED
    )


def _load(workspace: Any) -> None:
    if not hasattr(workspace, "production_review_summary"):
        return
    shot_id = workspace._selected_shot_id
    if shot_id is None:
        workspace.production_review_status.setText("No Shot is selected.")
        workspace.production_acceptance_status.setText(
            "PHASE 19.4 NOT READY — no Shot is selected."
        )
        workspace.production_review_summary.clear()
        workspace.production_review_approve_button.setEnabled(False)
        workspace.production_review_changes_button.setEnabled(False)
        return
    provider_id = _provider_id(workspace)
    persisted = workspace.production_review_service.current_review(
        shot_id,
        provider_id,
    )
    review = persisted or workspace.production_review_service.inspect(
        shot_id,
        provider_id,
    )
    _render(workspace, review, persisted is not None)


def _validate(workspace: Any) -> None:
    shot_id = workspace._selected_shot_id
    if shot_id is None:
        return
    _render(
        workspace,
        workspace.production_review_service.validate(
            shot_id,
            _provider_id(workspace),
        ),
        False,
    )


def _approve(workspace: Any) -> None:
    shot_id = workspace._selected_shot_id
    if shot_id is None:
        return
    try:
        review = workspace.production_review_service.approve(
            shot_id,
            provider_id=_provider_id(workspace),
            reviewed_by=workspace.production_review_reviewer.text(),
            notes=workspace.production_review_notes.toPlainText(),
        )
    except ValueError as exc:
        QMessageBox.warning(workspace, "Production Review", str(exc))
        _load(workspace)
        return
    _render(workspace, review, True)


def _request_changes(workspace: Any) -> None:
    shot_id = workspace._selected_shot_id
    if shot_id is None:
        return
    try:
        review = workspace.production_review_service.require_changes(
            shot_id,
            provider_id=_provider_id(workspace),
            reviewed_by=workspace.production_review_reviewer.text(),
            notes=workspace.production_review_notes.toPlainText(),
        )
    except ValueError as exc:
        QMessageBox.warning(workspace, "Production Review", str(exc))
        return
    _render(workspace, review, True)


def _build_tab(workspace: Any) -> None:
    tab = QWidget(workspace.compiler_tabs)
    layout = QVBoxLayout(tab)
    group = QGroupBox("Production Package Review & Validation", tab)
    group_layout = QVBoxLayout(group)
    guidance = QLabel(
        "Final automated readiness validation and explicit human approval gate. "
        "This phase does not submit provider jobs.",
        group,
    )
    guidance.setWordWrap(True)
    group_layout.addWidget(guidance)
    workspace.production_review_status = QLabel("", group)
    workspace.production_review_status.setWordWrap(True)
    group_layout.addWidget(workspace.production_review_status)
    workspace.production_acceptance_status = QLabel("", group)
    workspace.production_acceptance_status.setWordWrap(True)
    group_layout.addWidget(workspace.production_acceptance_status)
    workspace.production_review_summary = QTextEdit(group)
    workspace.production_review_summary.setReadOnly(True)
    group_layout.addWidget(workspace.production_review_summary, 1)
    reviewer_row = QHBoxLayout()
    reviewer_row.addWidget(QLabel("Reviewer", group))
    workspace.production_review_reviewer = QLineEdit(group)
    workspace.production_review_reviewer.setPlaceholderText(
        "Required for a human decision"
    )
    reviewer_row.addWidget(workspace.production_review_reviewer, 1)
    group_layout.addLayout(reviewer_row)
    group_layout.addWidget(QLabel("Review notes", group))
    workspace.production_review_notes = QTextEdit(group)
    workspace.production_review_notes.setMaximumHeight(90)
    group_layout.addWidget(workspace.production_review_notes)
    actions = QHBoxLayout()
    workspace.production_review_validate_button = QPushButton(
        "Validate Package",
        group,
    )
    workspace.production_review_approve_button = QPushButton(
        "Approve for Production",
        group,
    )
    workspace.production_review_changes_button = QPushButton(
        "Request Changes",
        group,
    )
    for button in (
        workspace.production_review_validate_button,
        workspace.production_review_approve_button,
        workspace.production_review_changes_button,
    ):
        actions.addWidget(button)
    actions.addStretch(1)
    group_layout.addLayout(actions)
    layout.addWidget(group, 1)
    review_index = workspace.compiler_tabs.addTab(tab, "Production Review")
    workspace.production_review_validate_button.clicked.connect(
        lambda: _validate(workspace)
    )
    workspace.production_review_approve_button.clicked.connect(
        lambda: _approve(workspace)
    )
    workspace.production_review_changes_button.clicked.connect(
        lambda: _request_changes(workspace)
    )
    workspace.compiler_tabs.currentChanged.connect(
        lambda index: _load(workspace) if index == review_index else None
    )


def install_production_package_review_workspace() -> None:
    """Install the final Phase 19.4 review tab on Production Planning."""
    from .universal_production_description_compiler_workspace import (
        UniversalProductionDescriptionCompilerWorkspace,
    )

    workspace_type: Any = UniversalProductionDescriptionCompilerWorkspace
    original_init = workspace_type.__init__
    original_selection = workspace_type._selection_changed
    original_footer = workspace_type._update_future_footer

    def reviewed_init(workspace: Any, *args: Any, **kwargs: Any) -> None:
        original_init(workspace, *args, **kwargs)
        workspace.production_review_service = ProductionPackageReviewService(
            workspace.projects,
            workspace.packages,
            workspace.universal_compiler,
            workspace.provider_compiler,
        )
        workspace.production_acceptance_service = ProductionPackageAcceptanceService(
            workspace.packages,
            workspace.production_review_service,
        )
        _build_tab(workspace)
        _load(workspace)

    def reviewed_selection(workspace: Any) -> None:
        original_selection(workspace)
        _load(workspace)

    def reviewed_footer(workspace: Any) -> None:
        original_footer(workspace)
        for label in workspace.findChildren(QLabel):
            if "final Production Package Validation" in label.text():
                label.setText(
                    "Phase 19.4 compilation is complete. Production Review is the "
                    "final validation and human approval gate before later provider "
                    "execution."
                )
                label.setWordWrap(True)

    workspace_type.__init__ = reviewed_init
    workspace_type._selection_changed = reviewed_selection
    workspace_type._update_future_footer = reviewed_footer
    workspace_type._load_production_review = _load
