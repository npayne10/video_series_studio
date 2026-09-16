"""Structural Shot refresh protection for Action & Performance authoring."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton

from vscs.application.action_performance import (
    ActionPerformanceDraft,
    ActionPerformanceStatus,
    ActionPerformanceStructuralChange,
)


def _change_labels(changes: tuple[ActionPerformanceStructuralChange, ...]) -> str:
    return ", ".join(change.label for change in changes)


def _stale_message(
    draft: ActionPerformanceDraft,
    changes: tuple[ActionPerformanceStructuralChange, ...],
) -> str:
    if draft.status is ActionPerformanceStatus.READY:
        return (
            "Action & Performance is Ready but no longer current against the governed Shot. "
            "Return it to Draft before choosing Rebase / Preserve or Rebuild from Current Shot."
        )
    if changes:
        labels = _change_labels(changes)
        return (
            "Action & Performance is structurally stale or its original Shot authority cannot be "
            f"verified ({labels}). Rebase / Preserve is blocked. Use Rebuild from Current Shot "
            "to reload the governed narrative, dialogue, continuity and runtime before review."
        )
    return (
        "Action & Performance source provenance changed, but its captured structural Shot "
        "authority is unchanged. Rebase / Preserve may update provenance without replacing "
        "authored content. Rebuild from Current Shot remains available if a full source reset "
        "is preferred."
    )


def install_action_performance_authority_integrity() -> None:
    """Install structural authority guards on the Production Planning Action tab."""
    from .production_package_workspace import ProductionPackageWorkspace

    workspace_type: Any = ProductionPackageWorkspace
    if getattr(workspace_type, "_action_authority_integrity_installed", False):
        return

    original_init = workspace_type.__init__
    original_build_action_tab = workspace_type._build_action_tab
    original_load_draft = workspace_type._load_draft
    original_set_editor_enabled = workspace_type._set_editor_enabled

    def build_action_tab(workspace: Any) -> None:
        original_build_action_tab(workspace)
        workspace.refresh_source_button.setText("Rebase / Preserve")
        workspace.refresh_source_button.setToolTip(
            "Update source provenance only when structural governed Shot authority is unchanged; "
            "authored content is preserved."
        )
        action_group = workspace.refresh_source_button.parentWidget()
        if action_group is None:
            raise RuntimeError("Action & Performance group is unavailable")
        workspace.rebuild_source_button = QPushButton("Rebuild from Current Shot", action_group)
        workspace.rebuild_source_button.setToolTip(
            "Replace Shot-derived narrative, dialogue, continuity and timing from the current "
            "governed Shot while preserving Performance direction."
        )

        group_layout = action_group.layout()
        if group_layout is None:
            raise RuntimeError("Action & Performance layout is unavailable")
        inserted = False
        for index in range(group_layout.count()):
            layout_item = group_layout.itemAt(index)
            nested = layout_item.layout() if layout_item is not None else None
            if not isinstance(nested, QHBoxLayout):
                continue
            refresh_index = nested.indexOf(workspace.refresh_source_button)
            if refresh_index >= 0:
                nested.insertWidget(refresh_index + 1, workspace.rebuild_source_button)
                inserted = True
                break
        if not inserted:
            raise RuntimeError("Action & Performance action row is unavailable")

    def load_draft(workspace: Any) -> None:
        original_load_draft(workspace)
        rebuild_button = getattr(workspace, "rebuild_source_button", None)
        if rebuild_button is None:
            return
        if workspace._selected_shot_id is None:
            rebuild_button.setEnabled(False)
            return
        draft = workspace.action_performance.draft(workspace._selected_shot_id)
        if draft is None:
            rebuild_button.setEnabled(False)
            return

        stale = not workspace.action_performance.is_current(draft)
        ready = draft.status is ActionPerformanceStatus.READY
        if not stale:
            rebuild_button.setEnabled(False)
            return

        changes = workspace.action_performance.structural_changes(draft)
        workspace.action_status.setText(_stale_message(draft, changes))
        workspace.refresh_source_button.setEnabled(not ready and not changes)
        rebuild_button.setEnabled(not ready)

    def set_editor_enabled(workspace: Any, enabled: bool) -> None:
        original_set_editor_enabled(workspace, enabled)
        rebuild_button = getattr(workspace, "rebuild_source_button", None)
        if rebuild_button is not None and not enabled:
            rebuild_button.setEnabled(False)

    def rebuild_source(workspace: Any) -> None:
        if workspace._selected_shot_id is None:
            return
        answer = QMessageBox.question(
            workspace,
            "Rebuild Action & Performance from Current Shot",
            "This will replace Temporal narrative, Spoken content / dialogue, Opening state, "
            "Closing state and Timing notes from the current governed Shot.\n\n"
            "Performance direction will be preserved.\n\n"
            "Continue with the rebuild?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        shot_id = workspace._selected_shot_id
        workspace._run(
            lambda: workspace.action_performance.rebuild_from_current_package(shot_id),
            "Action & Performance",
        )

    def init(workspace: Any, *args: Any, **kwargs: Any) -> None:
        original_init(workspace, *args, **kwargs)
        workspace.rebuild_source_button.clicked.connect(lambda: rebuild_source(workspace))

    workspace_type._build_action_tab = build_action_tab
    workspace_type._load_draft = load_draft
    workspace_type._set_editor_enabled = set_editor_enabled
    workspace_type.__init__ = init
    workspace_type._action_authority_integrity_installed = True
