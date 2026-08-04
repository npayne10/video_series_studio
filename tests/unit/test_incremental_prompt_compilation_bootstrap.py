"""Bootstrap coverage for incremental prompt compilation services."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationScheduler,
    BatchPromptCompilationService,
    IncrementalCompilationHistory,
    IncrementalCompilationService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_shared_incremental_services(tmp_path: Path) -> None:
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
        history = application.services.require(IncrementalCompilationHistory)
        incremental = application.services.require(IncrementalCompilationService)
        batch = application.services.require(BatchPromptCompilationService)
        scheduler = application.services.require(BatchCompilationScheduler)

        assert incremental.history is history
        assert batch.incremental is incremental
        assert scheduler.compilation_service is batch
    finally:
        application.shutdown()
