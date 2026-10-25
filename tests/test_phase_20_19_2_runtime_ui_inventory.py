"""Phase 20.19.2: inspect the fully installed GUI, not base shell alone."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.runtime_ui_inventory import (
    collect_runtime_ui_inventory,
    write_runtime_ui_inventory,
)


def test_inventory_includes_dynamic_story_and_planning_workspaces(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        window = context.create_main_window()
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        inventory = collect_runtime_ui_inventory(window)
        workspaces = inventory["workspaces"]
        by_name = {row["name"]: row for row in workspaces}
        assert len(workspaces) == window.content_stack.count()
        assert by_name["Story"]["placeholder"] is False
        assert by_name["Production Planning"]["placeholder"] is False
        assert "View" in {menu["name"] for menu in inventory["menus"]}
        assert "Assets" in inventory["duplicate_menu_workspace_labels"]
        assert inventory["provider_called"] is False
        assert inventory["project_path_recorded"] is False

        path = write_runtime_ui_inventory(window, tmp_path / "inventory.json")
        assert json.loads(path.read_text(encoding="utf-8"))["workspaces"] == workspaces
        with pytest.raises(FileExistsError):
            write_runtime_ui_inventory(window, path)
    finally:
        context.shutdown()


def test_inventory_does_not_activate_menu_actions(
    qtbot: object, qapp: QApplication, tmp_path: Path
) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        window = context.create_main_window()
        qtbot.addWidget(window)  # type: ignore[attr-defined]
        before = window.navigation.currentRow()
        first = collect_runtime_ui_inventory(window)
        second = collect_runtime_ui_inventory(window)
        assert first == second
        assert window.navigation.currentRow() == before
        assert context.services.require(type(window.projects)).is_project_open is False
    finally:
        context.shutdown()
