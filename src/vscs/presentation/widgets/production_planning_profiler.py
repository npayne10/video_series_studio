"""Diagnostic timing profiler for Phase 19.4 Production Planning.

The profiler runs the same snapshot-cached refresh path as production and records
wall-clock timings for snapshot capture, compiler state lookups, selected-tab draft
loads and the total refresh. It intentionally changes no compiler persistence or
production authority semantics.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from time import perf_counter
from typing import Any

from PySide6.QtWidgets import QTableWidgetItem

from .production_planning_performance import ProductionPlanningSnapshot

_LOGGER = logging.getLogger("vscs.performance.production_planning")


def _timed[T](label: str, callback: Callable[[], T]) -> T:
    started = perf_counter()
    try:
        return callback()
    finally:
        elapsed = perf_counter() - started
        _LOGGER.info("PPROF %-38s %9.3f s", label, elapsed)


def _profiled_refresh(workspace: Any) -> None:
    """Run the snapshot-cached refresh while logging expensive boundaries."""
    total_started = perf_counter()
    selected = workspace._selected_shot_id

    if workspace.projects.is_project_open:

        def capture_snapshot() -> ProductionPlanningSnapshot:
            return ProductionPlanningSnapshot.capture(workspace)

        snapshot = _timed("snapshot.capture", capture_snapshot)
    else:
        snapshot = ProductionPlanningSnapshot((), (), {}, {})
    rows = snapshot.rows

    with snapshot.activate(workspace):
        previous_signal_state = workspace.package_table.blockSignals(True)
        workspace.package_table.setUpdatesEnabled(False)
        selected_row = -1
        try:
            workspace.package_table.setColumnCount(11)
            workspace.package_table.setHorizontalHeaderLabels(workspace._headers())
            workspace.package_table.setRowCount(len(rows))
            state_methods = (
                ("action", workspace._action_state),
                ("asset", workspace._asset_state),
                ("camera", workspace._camera_state),
                ("lighting", workspace._lighting_state),
                ("continuity", workspace._continuity_state),
                ("style", workspace._style_state),
                ("universal", workspace._universal_state),
                ("provider", workspace._provider_state),
            )
            for row, package in enumerate(rows):
                shot_id = package.shot_id
                states_list: list[Any] = []
                for name, method in state_methods:

                    def get_state(
                        method: Callable[[str], Any] = method,
                        shot_id: str = shot_id,
                    ) -> Any:
                        return method(shot_id)

                    states_list.append(
                        _timed(
                            f"state.{name}[{shot_id}]",
                            get_state,
                        )
                    )

                values = (
                    shot_id,
                    package.package_id,
                    *tuple(states_list),
                    package.provenance.integrated_package_id,
                )
                for column, value in enumerate(values):
                    workspace.package_table.setItem(row, column, QTableWidgetItem(str(value)))
                if shot_id == selected:
                    selected_row = row

            if selected_row < 0 and rows:
                selected_row = 0
            if selected_row >= 0:
                workspace.package_table.selectRow(selected_row)
        finally:
            workspace.package_table.setUpdatesEnabled(True)
            workspace.package_table.blockSignals(previous_signal_state)

        _timed("workspace.update_future_footer", workspace._update_future_footer)
        if selected_row >= 0:
            _profiled_load_selected_snapshot(workspace)
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

    _LOGGER.info("PPROF %-38s %9.3f s", "REFRESH TOTAL", perf_counter() - total_started)


def _profiled_load_selected_snapshot(workspace: Any) -> None:
    row = workspace.package_table.currentRow()
    if row < 0:
        return
    item = workspace.package_table.item(row, 0)
    if item is None:
        return
    workspace._selected_shot_id = item.text()
    shot_id = workspace._selected_shot_id

    def get_selected_package() -> Any:
        return workspace.packages.current_package(shot_id)

    package = _timed(
        f"selected.current_package[{shot_id}]",
        get_selected_package,
    )
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
        "_load_production_review",
    )
    for name in loaders:
        loader = getattr(workspace, name, None)
        if loader is not None:
            _timed(f"load.{name}[{shot_id}]", loader)


def install_production_planning_profiler() -> None:
    """Install diagnostic Production Planning timing instrumentation."""
    from .universal_production_description_compiler_workspace import (
        UniversalProductionDescriptionCompilerWorkspace,
    )

    workspace_type: Any = UniversalProductionDescriptionCompilerWorkspace
    workspace_type.refresh = _profiled_refresh
