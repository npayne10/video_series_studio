"""Bootstrap tests for the ComfyUI adapter foundation."""

from __future__ import annotations

from pathlib import Path

from vscs.application.rendering import RenderAdapterRegistry, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.infrastructure.rendering import ComfyUIAdapter


def test_bootstrap_registers_dry_run_comfyui_adapter(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        adapter = context.services.require(ComfyUIAdapter)
        registry = context.services.require(RenderAdapterRegistry)

        assert adapter.renderer is RendererKind.COMFYUI
        assert registry.contains(RendererKind.COMFYUI)
        assert registry.require(RendererKind.COMFYUI) is adapter
    finally:
        context.shutdown()
