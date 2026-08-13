"""Performance refinement for the full Phase 19.4 Production Planning workspace.

Production Planning compilers share the same planning and Production Package state.
A refresh therefore captures that state once and temporarily serves repeated
``current_package()``, ``list_packages()`` and planning-currentness queries from the
snapshot. This is especially important for Continuity, which needs the previous Shot
and otherwise repeats the same governed-planning resolution many times per refresh.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QTableWidgetItem


@dataclass(slots=True)
class ProductionPlanningSnapshot:
    """One immutable-in-practice read snapshot used for a single UI refresh."""

    integrated_history: tuple[Any, ...]
    production_history: tuple[Any, ...]
    current_integrated: dict[str, Any]
    current_packages: dict[str, Any]

    @classmethod
    def capture(cls, workspace: Any) -> ProductionPlanningSnapshot:
        """Resolve current planning/package state once for all compiler views."""
        planning = workspace.packages.planning
        integrated_history = tuple(planning.list_packages())
        shot_ids = sorted({item.shot_id for item in integrated_history})
        current_integrated: dict[str, Any] = {}

        planning_current = getattr(planning, "current_package", None)
        if callable(planning_current):
            for shot_id in shot_ids:
                integrated = planning_current(shot_id)
                if integrated is not None:
                    current_integrated[shot_id] = integrated
        else:
            for integrated in integrated_history:
                if planning.is_current(integrated):
                    current_integrated[integrated.shot_id] = integrated

        package_list = getattr(workspace.packages, "list_packages", None)
        production_values = list(package_list()) if callable(package_list) else []
        current_packages: dict[str, Any] = {}
        for shot_id, integrated in current_integrated.items():
            package = next(
                (
                    item
                    for item in reversed(production_values)
                    if item.shot_id == shot_id
                    and item.source_fingerprint == integrated.package_fingerprint
                ),
                None,
            )
            if package is None and not production_values:
                package = workspace.packages.current_package(shot_id)
            if package is None:
                package = workspace.packages.materialize(shot_id)
                production_values.append(package)
            current_packages[shot_id] = package

        return cls(
            integrated_history,
            tuple(production_values),
            current_integrated,
            current_packages,
        )

    @property
    def rows(self) -> tuple[Any, ...]:
        return tuple(self.current_packages[key] for key in sorted(self.current_packages))

    def previous_package(self, shot_id: str) -> Any | None:
        """Return the previous current Shot package without repository traversal."""
        normalized = shot_id.strip().upper()
        ordered = sorted(self.current_packages)
        if normalized not in ordered:
            return None
        index = ordered.index(normalized)
        return self.current_packages[ordered[index - 1]] if index else None

    @contextmanager
    def activate(self, workspace: Any) -> Iterator[None]:
        """Serve repeated package/planning reads from this refresh snapshot."""
        packages = workspace.packages
        planning = packages.planning
        original_package_list = getattr(packages, "list_packages", None)
        original_package_current = packages.current_package
        original_planning_list = planning.list_packages
        original_planning_current = getattr(planning, "current_package", None)
        original_planning_is_current = planning.is_current

        def cached_package_list(*, shot_id: str | None = None) -> tuple[Any, ...]:
            values = self.production_history
            if shot_id is None:
                return values
            normalized = shot_id.strip().upper()
            return tuple(item for item in values if item.shot_id == normalized)

        def cached_package_current(shot_id: str) -> Any | None:
            return self.current_packages.get(shot_id.strip().upper())

        def cached_planning_list(*, shot_id: str | None = None) -> tuple[Any, ...]:
            values = self.integrated_history
            if shot_id is None:
                return values
            normalized = shot_id.strip().upper()
            return tuple(item for item in values if item.shot_id == normalized)

        def cached_planning_current(shot_id: str) -> Any | None:
            return self.current_integrated.get(shot_id.strip().upper())

        def cached_planning_is_current(package: Any) -> bool:
            current = self.current_integrated.get(package.shot_id)
            return current is not None and current.package_id == package.package_id

        if original_package_list is not None:
            packages.list_packages = cached_package_list
        packages.current_package = cached_package_current
        planning.list_packages = cached_planning_list
        if original_planning_current is not None:
            planning.current_package = cached_planning_current
        planning.is_current = cached_planning_is_current
        try:
            yield
        finally:
            if original_package_list is not None:
                packages.list_packages = original_package_list
            packages.current_package = original_package_current
            planning.list_packages = original_planning_list
            if original_planning_current is not None:
                planning.current_package = original_planning_current
            planning.is_current = original_planning_is_current


def _optimized_refresh(workspace: Any) -> None:
    """Refresh the final Production Planning workspace from one package snapshot."""
    selected = workspace._selected_shot_id
    snapshot = (
        ProductionPlanningSnapshot.capture(workspace)
        if workspace.projects.is_project_open
        else ProductionPlanningSnapshot((), (), {}, {})
    )
    rows = snapshot.rows

    with snapshot.activate(workspace):
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

    workspace_type: Any = UniversalProductionDescriptionCompilerWorkspace
    workspace_type.refresh = _optimized_refresh
