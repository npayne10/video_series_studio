"""Bootstrap coverage for the batch compilation scheduler."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationScheduler,
    BatchPromptCompilationService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_scheduler_with_shared_batch_service(tmp_path: Path) -> None:
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
        scheduler = application.services.require(BatchCompilationScheduler)
        batch_service = application.services.require(BatchPromptCompilationService)

        assert scheduler.compilation_service is batch_service
        assert scheduler.snapshot().entries == ()
    finally:
        application.shutdown()
