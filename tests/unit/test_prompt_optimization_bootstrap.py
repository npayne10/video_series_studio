"""Bootstrap coverage for prompt optimisation services."""

from pathlib import Path

from vscs.application.prompt_graph import (
    PromptOptimizationService,
    RendererPromptCompiler,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_shared_prompt_optimization_service(
    tmp_path: Path,
) -> None:
    application = build_application_context(
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
        optimizer = application.services.require(PromptOptimizationService)
        renderer = application.services.require(RendererPromptCompiler)

        assert optimizer.renderer_compiler is renderer
    finally:
        application.shutdown()
