"""Bootstrap coverage for renderer profiles and prompt preview services."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptPreviewService,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_prompt_profile_and_preview_services(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.toml",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        registry = context.services.require(RendererPromptProfileRegistry)
        profile = registry.resolve(RendererKind.COMFYUI, QualityLevel.PRODUCTION)

        assert profile.profile_id == "comfyui_production_v1"
        assert context.services.require(RendererPromptCompiler)
        assert context.services.require(PromptPreviewService)
    finally:
        context.shutdown()
