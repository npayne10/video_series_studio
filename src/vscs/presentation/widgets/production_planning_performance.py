"""Performance refinement for the full Phase 19.4 Production Planning workspace.

The compiler workspace was built incrementally through inheritance.  Calling every
intermediate ``refresh()`` rebuilt the same table repeatedly and caused Qt selection
signals to reload all compiler tabs several times per user action.  The installed
refresh below treats the current Production Package set as one snapshot, rebuilds
the final table once, suppresses intermediate selection signals, and loads each
selected compiler view once.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QTableWidgetItem


def _optimized_refresh(workspace: Any) -> None:
    """Refresh the final Production Planning workspace from one package snapshot."""
    selected = workspace._selected_shot_id
    rows: list[Any] = []
    if workspace.projects.is_project_open:
        for integrated in workspace.packages.planning.list_packages():
            if not workspace.packages.planning.is_current(integrated):
                continue
            package = workspace.packages.current_package(integrated.shot_id)
            if package is None:
                package = workspace.packages.materialize(integrated.shot_id)
            rows.append(package)

    previous_signal_state = workspace.package_table.blockSignals(True)
    workspace.package_table.setUpdatesEnabled(False)
    selected_row = -1
    try:
        workspace.package_table.setColumnCount(11)
        workspace.package_table.setHorizontalHeaderLabels(workspace._headers())
        workspace.package_table.setRowCount(len(rows))
        for row, package in enumerate(rows):
            values = (
                package.shot_id,
                package.package_id,
                workspace._action_state(package.shot_id),
                workspace._asset_state(package.shot_id),
                workspace._camera_state(package.shot_id),
                workspace._lighting_state(package.shot_id),
                workspace._continuity_state(package.shot_id),
                workspace._style_state(package.shot_id),
                workspace._universal_state(package.shot_id),
                workspace._provider_state(package.shot_id),
                package.provenance.integrated_package_id,
            )
            for column, value in enumerate(values):
                workspace.package_table.setItem(row, column, QTableWidgetItem(str(value)))
            if package.shot_id == selected:
                selected_row = row

        if selected_row < 0 and rows:
            selected_row = 0
        if selected_row >= 0:
            workspace.package_table.selectRow(selected_row)
    finally:
        workspace.package_table.setUpdatesEnabled(True)
        workspace.package_table.blockSignals(previous_signal_state)

    workspace._update_future_footer()
    if selected_row >= 0:
        _load_selected_snapshot(workspace)
    else:
        workspace._selected_shot_id = None
        workspace.package_summary.setText(
            "No current approved Integrated Planning Packages are available. "
            "Complete Planning Review for a Shot first."
        )
        workspace.action_status.clear()
        workspace.asset_status.clear()
        workspace._clear_editor()
        workspace._clear_asset_editor()
        workspace._set_editor_enabled(False)
        workspace._set_asset_editor_enabled(False)


def _load_selected_snapshot(workspace: Any) -> None:
    """Load each selected compiler view exactly once after a snapshot refresh."""
    row = workspace.package_table.currentRow()
    if row < 0:
        return
    item = workspace.package_table.item(row, 0)
    if item is None:
        return
    workspace._selected_shot_id = item.text()
    package = workspace.packages.current_package(workspace._selected_shot_id)
    if package is None:
        return

    workspace.package_summary.setText(
        f"<b>{package.shot_id}</b><br>Production Package: {package.package_id}<br>"
        f"Status: {package.status.value.title()} &nbsp; | &nbsp; "
        f"Planning source: {package.provenance.integrated_package_id}"
    )

    loaders = (
        "_load_draft",
        "_load_asset_draft",
        "_load_camera_draft",
        "_load_lighting_draft",
        "_load_continuity_draft",
        "_load_style_draft",
        "_load_universal_draft",
        "_load_provider_draft",
    )
    for name in loaders:
        loader = getattr(workspace, name, None)
        if loader is not None:
            loader()


def install_production_planning_performance() -> None:
    """Install the optimized refresh on the complete Phase 19.4 workspace."""
    from .universal_production_description_compiler_workspace import (
        UniversalProductionDescriptionCompilerWorkspace,
    )

    setattr(UniversalProductionDescriptionCompilerWorkspace, "refresh", _optimized_refresh)
