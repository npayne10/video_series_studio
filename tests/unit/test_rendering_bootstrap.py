"""Tests for rendering contract dependency registration."""

from pathlib import Path

from vscs.application.rendering import (
    QualityLevel,
    QualityProfileRegistry,
    RenderAdapterRegistry,
    RendererKind,
    RenderingContracts,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_rendering_contract_foundation(tmp_path: Path) -> None:
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

    contracts = context.services.require(RenderingContracts)
    adapters = context.services.require(RenderAdapterRegistry)
    profiles = context.services.require(QualityProfileRegistry)

    assert contracts.version == "17.4.0.5"
    assert adapters.renderers() == (RendererKind.COMFYUI,)
    assert profiles.require(QualityLevel.PREVIEW).priority == 50
    assert profiles.require(QualityLevel.PRODUCTION).priority == 100

    context.shutdown()
