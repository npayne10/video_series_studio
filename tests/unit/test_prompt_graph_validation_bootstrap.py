"""Bootstrap tests for prompt graph validation services."""

from pathlib import Path

from vscs.application.prompt_graph import PromptGraphValidator
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_prompt_graph_validator(tmp_path: Path) -> None:
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

    validator = context.services.require(PromptGraphValidator)

    assert isinstance(validator, PromptGraphValidator)
    context.shutdown()
