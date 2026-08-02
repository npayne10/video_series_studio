"""Application composition root for VSCS desktop startup and frontend tests."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import (
    CanonicalReferenceRepository,
    CanonicalReferenceService,
    CAPGeneratorService,
    CAPRepository,
    CAPService,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.ai import (
    AICredentialStore,
    CAPGenerationProvider,
    OpenAICAPGenerationProvider,
    TemplateCAPGenerationProvider,
)
from vscs.infrastructure.configuration import (
    AIProvider,
    ConfigurationService,
    EnvironmentManager,
)
from vscs.infrastructure.database import DatabaseManager
from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.plugins import PluginManager
from vscs.infrastructure.services import ApplicationServices

if TYPE_CHECKING:
    from vscs.presentation.windows.main_window import MainWindow


class StartupMode(StrEnum):
    """Supported application startup profiles."""

    NORMAL = "normal"
    DEVELOPMENT = "development"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class BootstrapOptions:
    """Policy controlling construction of the VSCS application graph."""

    mode: StartupMode = StartupMode.NORMAL
    config_path: Path | None = None
    plugin_root: Path | None = None
    configure_logging: bool = True
    discover_plugins: bool = True
    load_plugins: bool = True
    validate_environment: bool = True


@dataclass(slots=True)
class ApplicationContext:
    """Managed application dependency graph and lifecycle boundary."""

    services: ApplicationServices
    configuration: ConfigurationService
    environment: EnvironmentManager
    database: DatabaseManager
    plugins: PluginManager
    logging_service: LoggingService | None = None
    logger: logging.Logger | None = None
    environment_messages: tuple[str, ...] = ()
    _shutdown: bool = False

    @property
    def is_shutdown(self) -> bool:
        """Return whether application resources have been released."""
        return self._shutdown

    def create_main_window(self) -> MainWindow:
        """Create the real VSCS main window without starting the event loop."""
        from vscs.presentation.windows.main_window import MainWindow

        return MainWindow(self.services)

    def shutdown(self) -> None:
        """Release application resources exactly once."""
        if self._shutdown:
            return
        self.plugins.shutdown()
        self.database.close()
        if self.logger is not None:
            self.logger.info("VSCS application context stopped")
        self.services.clear()
        if self.logging_service is not None:
            logging.shutdown()
        self._shutdown = True

    def __enter__(self) -> ApplicationContext:
        return self

    def __exit__(self, *_args: object) -> None:
        self.shutdown()


def build_application_context(
    options: BootstrapOptions | None = None,
) -> ApplicationContext:
    """Build and validate the complete VSCS dependency graph."""
    selected = options or BootstrapOptions()
    configuration = ConfigurationService(selected.config_path)
    configuration.load()
    environment = EnvironmentManager(configuration.settings)
    environment.apply()

    services = ApplicationServices()
    services.register(ConfigurationService, configuration)
    services.register(EnvironmentManager, environment)

    logging_service: LoggingService | None = None
    logger: logging.Logger | None = None
    if selected.configure_logging:
        settings = configuration.settings.logging
        root = configuration.settings.environment.logs_root.expanduser().resolve(strict=False)
        logging_service = LoggingService(
            root,
            level=settings.level,
            console_enabled=settings.console_enabled,
            max_file_size_bytes=settings.max_file_size_bytes,
            backup_count=settings.backup_count,
        )
        logger = logging_service.configure()
        services.register(LoggingService, logging_service)

    database = services.register(DatabaseManager, DatabaseManager())
    projects = services.register(ProjectService, ProjectService(configuration, database))
    asset_repository = services.register(AssetRepository, AssetRepository(database))
    assets = services.register(AssetService, AssetService(projects, asset_repository))
    cap_repository = services.register(CAPRepository, CAPRepository(database))
    caps = services.register(CAPService, CAPService(assets, cap_repository))
    reference_repository = services.register(
        CanonicalReferenceRepository,
        CanonicalReferenceRepository(database),
    )
    services.register(
        CanonicalReferenceService,
        CanonicalReferenceService(caps, reference_repository),
    )
    provider = _cap_provider(configuration, selected.mode)
    services.register(
        CAPGeneratorService,
        CAPGeneratorService(assets, caps, provider),
    )

    plugins = PluginManager(configuration, services, selected.plugin_root)
    services.register(PluginManager, plugins)
    if selected.discover_plugins:
        plugins.discover()
    if selected.load_plugins:
        plugins.load_enabled()

    messages: tuple[str, ...] = ()
    if selected.validate_environment:
        health = environment.healthcheck()
        if not health.ready:
            messages = tuple(health.messages)
            if logger is not None:
                logger.warning("VSCS environment health check: %s", "; ".join(messages))

    if logger is not None:
        logger.info("VSCS dependency graph initialized in %s mode", selected.mode.value)
    return ApplicationContext(
        services=services,
        configuration=configuration,
        environment=environment,
        database=database,
        plugins=plugins,
        logging_service=logging_service,
        logger=logger,
        environment_messages=messages,
    )


def _cap_provider(
    configuration: ConfigurationService,
    mode: StartupMode,
) -> CAPGenerationProvider:
    """Build the selected CAP provider, using deterministic templates in tests."""
    if mode is StartupMode.TEST:
        return TemplateCAPGenerationProvider()
    settings = configuration.settings.ai
    if settings.provider is AIProvider.OPENAI:
        try:
            api_key = AICredentialStore().get_openai_api_key()
            return OpenAICAPGenerationProvider(
                api_key=api_key,
                model=settings.openai_model,
            )
        except (RuntimeError, ValueError):
            return TemplateCAPGenerationProvider()
    return TemplateCAPGenerationProvider()
