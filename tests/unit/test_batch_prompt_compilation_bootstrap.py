"""Bootstrap coverage for the batch prompt compilation service."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchPromptCompilationService,
    PromptGraphBuilder,
    PromptGraphCompiler,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_batch_service_with_shared_dependencies(
    tmp_path: Path,
) -> None:
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
        service = context.services.require(BatchPromptCompilationService)

        assert service.builder is context.services.require(PromptGraphBuilder)
        assert service.graph_compiler is context.services.require(PromptGraphCompiler)
        assert service.profile_registry is context.services.require(RendererPromptProfileRegistry)
        assert service.renderer_compiler is context.services.require(RendererPromptCompiler)
    finally:
        context.shutdown()
