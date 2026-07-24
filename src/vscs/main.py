"""VSCS application entry point."""

from __future__ import annotations

import logging
import sys
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationError, ConfigurationService
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.windows.main_window import MainWindow


def _install_exception_hook(logger: logging.Logger) -> None:
    """Log uncaught exceptions before delegating to Python's default hook."""
    default_hook = sys.excepthook

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            default_hook(exception_type, exception, traceback)
            return
        logger.critical(
            "Unhandled exception",
            exc_info=(exception_type, exception, traceback),
        )
        default_hook(exception_type, exception, traceback)

    sys.excepthook = handle_exception


def main() -> int:
    """Launch the VSCS desktop application."""
    application = QApplication(sys.argv)
    application.setApplicationName("Video Series Studio")
    application.setOrganizationName("VSCS")

    services = ApplicationServices()

    configuration = ConfigurationService()
    try:
        configuration.load()
    except ConfigurationError as exc:
        QMessageBox.critical(None, "Configuration Error", str(exc))
        return 1
    services.register(ConfigurationService, configuration)

    logging_settings = configuration.settings.logging
    logging_service = LoggingService(
        configuration.config_path.parent / "logs",
        level=logging_settings.level,
        console_enabled=logging_settings.console_enabled,
        max_file_size_bytes=logging_settings.max_file_size_bytes,
        backup_count=logging_settings.backup_count,
    )
    try:
        logger = logging_service.configure()
    except (OSError, ValueError) as exc:
        QMessageBox.critical(None, "Logging Error", f"Unable to initialize logging: {exc}")
        return 1
    services.register(LoggingService, logging_service)

    database_manager = DatabaseManager()
    services.register(DatabaseManager, database_manager)
    project_service = ProjectService(configuration, database_manager)
    services.register(ProjectService, project_service)

    _install_exception_hook(logger)
    logger.info("Video Series Studio starting")
    logger.info("Configuration loaded from %s", configuration.config_path)
    logger.info("Application services initialized: %s", len(services))

    window = MainWindow(services)
    window.show()
    exit_code = application.exec()

    database_manager.close()
    logger.info("Video Series Studio stopped with exit code %s", exit_code)
    services.clear()
    logging.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
