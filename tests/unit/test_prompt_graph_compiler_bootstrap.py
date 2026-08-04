"""Bootstrap coverage for the prompt graph compiler."""

from pathlib import Path

from vscs.application.prompt_graph import PromptGraphCompiler, PromptGraphValidator
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_prompt_graph_compiler(tmp_path: Path) -> None:
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "config.yaml",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        compiler = context.services.require(PromptGraphCompiler)
        validator = context.services.require(PromptGraphValidator)
        assert compiler.validator is validator
    finally:
        context.shutdown()
