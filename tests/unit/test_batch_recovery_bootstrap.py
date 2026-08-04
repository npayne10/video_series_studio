"""Bootstrap coverage for batch recovery services."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationScheduler,
    BatchRecoveryService,
    BatchRecoveryStore,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_shared_recovery_services(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.toml"
    application = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=settings_path,
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    try:
        store = application.services.require(BatchRecoveryStore)
        recovery = application.services.require(BatchRecoveryService)
        scheduler = application.services.require(BatchCompilationScheduler)

        assert recovery.store is store
        assert scheduler.recovery_service is recovery
        assert store.path == tmp_path / "recovery" / "batch_compilation.json"
    finally:
        application.shutdown()
