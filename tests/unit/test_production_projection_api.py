"""Public API and bootstrap tests for Phase 18.2.11.2.8."""

from pathlib import Path

from vscs.application.caps import ProductionProjectionService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.caps import ProductionProjection, ProductionProjectionResult


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


def test_projection_contract_is_exported_through_public_cap_package() -> None:
    assert ProductionProjectionResult is ProductionProjection


def test_bootstrap_registers_shared_production_projection_service(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))

    service = context.services.require(ProductionProjectionService)

    assert isinstance(service, ProductionProjectionService)
    context.shutdown()
