"""UI contract coverage for the Asset Manager readiness column."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.application.assets import AssetService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate


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


def test_main_window_installs_asset_readiness_column(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.asset_manager.table.columnCount() == 6
    assert window.asset_manager.table.horizontalHeaderItem(5).text() == "Readiness"
    assert not window.asset_manager.table.isSortingEnabled()
    assert window.asset_readiness_service is not None
    assert window.cap_readiness_button is not None
    context.shutdown()


def test_readiness_column_preserves_asset_row_identity_during_refresh(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    """Header sorting must not split partially populated assets across table rows."""
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    expected = {
        "CAP-CHR-001": ("Commander James Spence", "character"),
        "CAP-SHP-001": ("Iron Horizon", "ship"),
        "CAP-VEH-001": ("Hangar Tug", "vehicle"),
    }
    for asset_id, (name, category) in expected.items():
        assets.create(
            AssetCreate(
                asset_id=asset_id,
                name=name,
                category=AssetCategory(category),
            )
        )

    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]
    window.asset_manager.refresh()

    table = window.asset_manager.table
    observed: dict[str, tuple[str, str]] = {}
    for row in range(table.rowCount()):
        asset_id = table.item(row, 0).text()
        observed[asset_id] = (table.item(row, 1).text(), table.item(row, 2).text())

    assert observed == expected
    assert table.rowCount() == len(expected)
    context.shutdown()
