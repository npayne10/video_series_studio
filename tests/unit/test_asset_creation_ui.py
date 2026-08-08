"""UI contract coverage for Phase 18.2.11.2.4 Asset Creation Integration."""

from pathlib import Path

from PySide6.QtWidgets import QApplication

from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.presentation.widgets.asset_manager import AssetEditorDialog


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


def test_new_asset_dialog_exposes_master_reference_contract(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    dialog = AssetEditorDialog(tmp_path)
    qtbot.addWidget(dialog)  # type: ignore[attr-defined]

    assert dialog.windowTitle() == "New Asset"
    assert "approved ChatGPT master" in dialog.file_path.placeholderText()
    assert "approved ChatGPT Master Canonical Reference" in dialog.master_confirmation.text()
    assert not dialog.master_confirmation.isChecked()


def test_main_window_wires_canonical_asset_creation_services(
    qtbot: object,
    qapp: QApplication,
    tmp_path: Path,
) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)  # type: ignore[attr-defined]

    assert window.asset_manager.canonical_creation is not None
    assert window.asset_manager.table.horizontalHeaderItem(4).text() == "MASTER"
    context.shutdown()
