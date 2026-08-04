"""Bootstrap coverage for batch observability services."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationHistory,
    BatchCompilationScheduler,
    BatchProgressTracker,
    BatchReportingService,
    BatchStatisticsService,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def test_bootstrap_registers_shared_batch_observability_services(tmp_path: Path) -> None:
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
        tracker = application.services.require(BatchProgressTracker)
        history = application.services.require(BatchCompilationHistory)
        statistics = application.services.require(BatchStatisticsService)
        reporting = application.services.require(BatchReportingService)

        assert scheduler.progress_tracker is tracker
        assert scheduler.reporting_service is reporting
        assert reporting.history is history
        assert reporting.statistics_service is statistics
        assert statistics.history is history
    finally:
        application.shutdown()
