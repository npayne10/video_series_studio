"""UI contract coverage for the Asset Manager readiness column."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


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
    assert window.asset_readiness_service is not None
    assert window.cap_readiness_button is not None
    context.shutdown()
