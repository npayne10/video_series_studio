"""Tests for the reusable project asset picker."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.presentation.dialogs.asset_picker_dialog import AssetPickerDialog


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_asset_picker_browses_searches_and_filters(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(
        tmp_path / "Demo",
        name="Demo",
    )
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate(
            asset_id="CHR-JAMES",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            description="Guild commander",
        )
    )
    assets.create(
        AssetCreate(
            asset_id="SHP-IRON-HORIZON",
            name="Iron Horizon",
            category=AssetCategory.SHIP,
            description="Survey vessel",
        )
    )

    picker = AssetPickerDialog(assets)
    qtbot.addWidget(picker)  # type: ignore[attr-defined]
    picker.show()
    qapp.processEvents()

    assert picker.asset_tree.topLevelItemCount() == 2
    picker.search_edit.setText("James")
    qapp.processEvents()
    assert picker.asset_tree.topLevelItemCount() == 1
    assert picker.asset_tree.topLevelItem(0).text(1) == "CHR-JAMES"

    picker.search_edit.clear()
    ship_index = picker.category_combo.findData(AssetCategory.SHIP.value)
    picker.category_combo.setCurrentIndex(ship_index)
    qapp.processEvents()
    assert picker.asset_tree.topLevelItemCount() == 1
    item = picker.asset_tree.topLevelItem(0)
    picker.asset_tree.setCurrentItem(item)
    assert picker.selected_asset_id == "SHP-IRON-HORIZON"
    assert picker.select_button.isEnabled()

    context.shutdown()
