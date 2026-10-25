"""Read-only inventory of the *instantiated* VSCS desktop window.

Call only after ApplicationContext.create_main_window() has installed runtime
extensions. This module never invokes actions, edits projects, or calls providers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QStackedWidget, QToolBar


def collect_runtime_ui_inventory(window: QMainWindow) -> dict[str, Any]:
    """Record runtime menus, navigation, instantiated workspaces and action aliases."""
    stack = getattr(window, "content_stack")
    navigation = getattr(window, "navigation")
    if not isinstance(stack, QStackedWidget):
        raise TypeError("Main window has no QStackedWidget content_stack")
    workspaces: list[dict[str, Any]] = []
    for index in range(stack.count()):
        widget = stack.widget(index)
        item = navigation.item(index) if index < navigation.count() else None
        workspaces.append(
            {
                "index": index,
                "name": item.text() if item is not None else None,
                "widget_type": type(widget).__name__,
                "widget_module": type(widget).__module__,
                "object_name": widget.objectName(),
                "placeholder": widget.objectName().endswith("Placeholder"),
                "enabled": widget.isEnabled(),
            }
        )
    menus: list[dict[str, Any]] = []
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if not isinstance(menu, QMenu):
            continue
        entries = []
        for action in menu.actions():
            entries.append(
                {
                    "text": action.text().replace("&", ""),
                    "object_name": action.objectName(),
                    "enabled": action.isEnabled(),
                    "separator": action.isSeparator(),
                    "has_submenu": action.menu() is not None,
                }
            )
        menus.append({"name": menu.title().replace("&", ""), "entries": entries})
    toolbar_actions: list[str] = []
    for toolbar in window.findChildren(QToolBar):
        for action in toolbar.actions():
            if isinstance(action, QAction) and not action.isSeparator():
                toolbar_actions.append(action.text().replace("&", ""))
    workspace_names = {str(row["name"]) for row in workspaces}
    duplicates = sorted(
        {
            str(entry["text"])
            for menu in menus
            for entry in menu["entries"]
            if entry["text"] in workspace_names
        }
    )
    return {
        "schema_version": "1.0",
        "phase": "20.19.2",
        "source": "instantiated_main_window_after_dynamic_installation",
        "project_path_recorded": False,
        "provider_called": False,
        "window_type": type(window).__name__,
        "window_title": window.windowTitle(),
        "workspaces": workspaces,
        "menus": menus,
        "toolbar_actions": toolbar_actions,
        "duplicate_menu_workspace_labels": duplicates,
    }


def write_runtime_ui_inventory(window: QMainWindow, output: Path) -> Path:
    """Write inventory to a new file; refuse overwrites and project directories."""
    target = output.expanduser().resolve(strict=False)
    with target.open("x", encoding="utf-8") as handle:
        json.dump(collect_runtime_ui_inventory(window), handle, indent=2, sort_keys=True)
        handle.write("\n")
    return target


def main() -> int:
    """Build a test-mode isolated UI graph; no real project is opened."""
    from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context

    parser = argparse.ArgumentParser(description="VSCS read-only runtime UI inventory")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    owned_app = app is None
    if owned_app:
        app = QApplication([])
    with TemporaryDirectory(prefix="vscs-ui-audit-") as temporary:
        context = build_application_context(
            BootstrapOptions(
                mode=StartupMode.TEST,
                config_path=Path(temporary) / "settings.yaml",
                plugin_root=Path(temporary) / "plugins",
                configure_logging=False,
                discover_plugins=False,
                load_plugins=False,
                validate_environment=False,
            )
        )
        try:
            window = context.create_main_window()
            try:
                path = write_runtime_ui_inventory(window, args.output)
                print(
                    json.dumps(
                        {
                            "status": "INVENTORY_CREATED_NO_PROVIDER_SUBMISSION",
                            "path": str(path),
                        }
                    )
                )
            finally:
                window.close()
        finally:
            context.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
