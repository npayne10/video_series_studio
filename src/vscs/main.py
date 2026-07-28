"""VSCS application entry point."""

from __future__ import annotations
import logging
import sys
from types import TracebackType

from PySide6.QtWidgets import QApplication, QMessageBox

from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import (
    CAPGeneratorService,
    CAPRepository,
    CAPService,
    CanonicalReferenceRepository,
    CanonicalReferenceService,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.ai import (
    AICredentialStore,
    OpenAICAPGenerationProvider,
    TemplateCAPGenerationProvider,
)
from vscs.infrastructure.configuration import (
    AIProvider,
    ConfigurationError,
    ConfigurationService,
    EnvironmentManager,
)
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.plugins import PluginManager
from vscs.infrastructure.services import ApplicationServices
from vscs.presentation.widgets import cap_manager as cap_manager_module
from vscs.presentation.widgets.cap_reference_deletion import (
    install_canonical_reference_deletion,
)
from vscs.presentation.widgets.cap_reference_evaluation import (
    install_canonical_image_evaluation,
)
from vscs.presentation.widgets.cap_reference_file_management import (
    install_canonical_reference_file_management,
)
from vscs.presentation.widgets.cap_reference_preview import PreviewCAPManagerWidget
from vscs.presentation.widgets.cap_reference_production_readiness import (
    install_production_readiness_evaluation,
)
from vscs.presentation.widgets.cap_reference_semantic_evaluation import (
    install_semantic_image_evaluation,
)

cap_manager_module.CAPManagerWidget = PreviewCAPManagerWidget
install_canonical_reference_file_management()
install_canonical_reference_deletion()
install_canonical_image_evaluation()
install_semantic_image_evaluation()
install_production_readiness_evaluation()

from vscs.presentation.windows.main_window import MainWindow  # noqa: E402


def _install_exception_hook(logger: logging.Logger) -> None:
    default_hook = sys.excepthook

    def handle_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            default_hook(exception_type, exception, traceback)
            return
        logger.critical("Unhandled exception", exc_info=(exception_type, exception, traceback))
        default_hook(exception_type, exception, traceback)

    sys.excepthook = handle_exception


def _build_cap_generation_provider(configuration: ConfigurationService) -> object:
    settings = configuration.settings.ai
    if settings.provider is AIProvider.OPENAI:
        api_key = AICredentialStore().get_openai_api_key()
        return OpenAICAPGenerationProvider(api_key=api_key, model=settings.openai_model)
    return TemplateCAPGenerationProvider()


def main() -> int:
    """Launch the VSCS desktop application."""
    application = QApplication(sys.argv)
    application.setApplicationName("Video Series Studio")
    application.setOrganizationName("VSCS")

    services = ApplicationServices()
    configuration = ConfigurationService()
    try:
        configuration.load()
        environment_manager = EnvironmentManager(configuration.settings)
        environment_manager.apply()
    except (ConfigurationError, OSError, ValueError) as exc:
        QMessageBox.critical(None, "Configuration Error", str(exc))
        return 1
    services.register(ConfigurationService, configuration)
    services.register(EnvironmentManager, environment_manager)

    logging_settings = configuration.settings.logging
    logging_root = configuration.settings.environment.logs_root.expanduser().resolve(strict=False)
    logging_service = LoggingService(
        logging_root,
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

    if configuration.settings.environment.validate_on_startup:
        health = environment_manager.healthcheck()
        if not health.ready:
            logger.warning("VSCS environment health check: %s", "; ".join(health.messages))
            QMessageBox.warning(
                None,
                "VSCS Environment",
                "VSCS started, but external rendering needs attention:\n\n"
                + "\n".join(f"• {message}" for message in health.messages),
            )

    database_manager = DatabaseManager()
    services.register(DatabaseManager, database_manager)
    project_service = ProjectService(configuration, database_manager)
    services.register(ProjectService, project_service)

    asset_repository = AssetRepository(database_manager)
    services.register(AssetRepository, asset_repository)
    asset_service = AssetService(project_service, asset_repository)
    services.register(AssetService, asset_service)

    cap_repository = CAPRepository(database_manager)
    services.register(CAPRepository, cap_repository)
    cap_service = CAPService(asset_service, cap_repository)
    services.register(CAPService, cap_service)

    canonical_reference_repository = CanonicalReferenceRepository(database_manager)
    services.register(CanonicalReferenceRepository, canonical_reference_repository)
    canonical_reference_service = CanonicalReferenceService(cap_service, canonical_reference_repository)
    services.register(CanonicalReferenceService, canonical_reference_service)

    try:
        cap_provider = _build_cap_generation_provider(configuration)
    except (RuntimeError, ValueError) as exc:
        QMessageBox.warning(
            None,
            "AI Configuration",
            "The configured AI provider could not be initialized. "
            f"The template provider will be used instead.\n\n{exc}",
        )
        cap_provider = TemplateCAPGenerationProvider()
    cap_generator = CAPGeneratorService(asset_service, cap_service, cap_provider)  # type: ignore[arg-type]
    services.register(CAPGeneratorService, cap_generator)

    plugin_manager = PluginManager(configuration, services)
    services.register(PluginManager, plugin_manager)
    plugin_manager.discover()
    plugin_manager.load_enabled()

    _install_exception_hook(logger)
    logger.info("Video Series Studio starting")
    logger.info("Configuration loaded from %s", configuration.config_path)
    logger.info("VSCS workspace: %s", configuration.settings.environment.workspace_root)
    logger.info("XCIC installation: %s", configuration.settings.environment.xcic_root)
    logger.info("ComfyUI URL: %s", configuration.settings.environment.comfyui_url)

    window = MainWindow(services)
    window.show()
    exit_code = application.exec()

    plugin_manager.shutdown()
    database_manager.close()
    logger.info("Video Series Studio stopped with exit code %s", exit_code)
    services.clear()
    logging.shutdown()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
