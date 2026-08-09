"""Composition-level acceptance guards for the completed CAP Production Contract."""

from pathlib import Path

from vscs.application.caps import ProductionProjectionService
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


def test_main_window_consumes_composition_root_projection_service(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    shared = context.services.require(ProductionProjectionService)
    window = context.create_main_window()
    qtbot.addWidget(window)

    assert window.production_projection is shared
    assert window.cap_manager.production_projection_service is shared
    assert window.cap_manager.readiness_service is shared.readiness

    context.shutdown()


def test_cap_workspace_keeps_single_governed_generation_entry_point(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)

    assert window.derived_reference_button is not None
    assert window.derived_reference_button.text() == "Generate Production References"
    assert window.cap_manager.production_projection_button.text() == "Production Projection"
    assert window.cap_readiness_button is not None
    assert window.cap_readiness_button.text() == "Readiness"

    context.shutdown()
