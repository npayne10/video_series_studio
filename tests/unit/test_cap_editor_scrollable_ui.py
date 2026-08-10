"""Regression coverage for the resizable, scrollable CAP production contract dialog."""

from pathlib import Path

from PySide6.QtWidgets import QScrollArea

from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate
from vscs.presentation.widgets.cap_manager import CAPEditorDialog


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


def test_cap_production_contract_is_resizable_and_scrollable(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-780",
            name="Scrollable Editor Ship",
            category=AssetCategory.SHIP,
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-SHP-780",
            title="Scrollable Editor Ship",
            canonical_description="Canonical ship.",
        )
    )

    window = context.create_main_window()
    qtbot.addWidget(window)
    dialog = CAPEditorDialog(
        caps,
        references,
        caps.get("CAP-SHP-780"),
        window.cap_manager,
    )
    qtbot.addWidget(dialog)

    scroll = dialog.findChild(QScrollArea, "capEditorScrollArea")
    assert scroll is not None
    assert scroll.widgetResizable()
    assert dialog.minimumWidth() == 600
    assert dialog.minimumHeight() == 420

    dialog.show()
    dialog.resize(700, 500)
    qtbot.wait(10)
    assert dialog.width() == 700
    assert dialog.height() == 500
    assert scroll.verticalScrollBar().maximum() > 0

    context.shutdown()
