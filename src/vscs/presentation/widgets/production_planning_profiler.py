"""Diagnostic timing profiler for Phase 19.4 Production Planning.

This module intentionally changes no compiler or persistence semantics. It wraps the
existing optimized workspace refresh and records wall-clock timings for the package
snapshot, compiler state lookups, and selected-tab draft loads. The output is sent
through the normal ``vscs.performance.production_planning`` logger so it appears in
both the configured VSCS log and the console when console logging is enabled.
"""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Callable, TypeVar

from PySide6.QtWidgets import QTableWidgetItem

_T = TypeVar("_T")
_LOGGER = logging.getLogger("vscs.performance.production_planning")


def _timed(label: str, callback: Callable[[], _T]) -> _T:
    started = perf_counter()
    try:
        return callback()
    finally:
        elapsed = perf_counter() - started
        _LOGGER.info("PPROF %-38s %9.3f s", label, elapsed)


def _profiled_refresh(workspace: Any) -> None:
    """Run the optimized refresh while logging every expensive boundary."""
    total_started = perf_counter()
    selected = workspace._selected_shot_id
    rows: list[Any] = []

    if workspace.projects.is_project_open:
        integrated_packages = _timed(
            "planning.list_packages",
            workspace.packages.planning.list_packages,
        )
        for integrated in integrated_packages:
            shot_id = integrated.shot_id
            current = _timed(
                f"planning.is_current[{shot_id}]",
                lambda integrated=integrated: workspace.packages.planning.is_current(
                    integrated
                ),
            )
            if not current:
                continue
            package = _timed(
                f"packages.current_package[{shot_id}]",
                lambda shot_id=shot_id: workspace.packages.current_package(shot_id),
            )
            if package is None:
                package = _timed(
                    f"packages.materialize[{shot_id}]",
                    lambda shot_id=shot_id: workspace.packages.materialize(shot_id),
                )
            rows.append(package)

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
            states = tuple(
                _timed(
                    f"state.{name}[{shot_id}]",
                    lambda method=method, shot_id=shot_id: method(shot_id),
                )
                for name, method in state_methods
            )
            values = (
                shot_id,
                package.package_id,
                *states,
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
    package = _timed(
        f"selected.current_package[{shot_id}]",
        lambda: workspace.packages.current_package(shot_id),
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
