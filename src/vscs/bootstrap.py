"""Application composition root for VSCS desktop startup and frontend tests."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from vscs.application.acpp import ACPPEditorService
from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import (
    CanonicalReferenceRepository,
    CanonicalReferenceService,
    CAPGeneratorService,
    CAPRepository,
    CAPService,
)
from vscs.application.projects import ProjectService
from vscs.application.prompt_graph import (
    BatchCompilationScheduler,
    BatchPromptCompilationService,
    PromptGraphBuilder,
    PromptGraphCompiler,
    PromptGraphDiagnosticsFactory,
    PromptGraphDiffer,
    PromptGraphRegistry,
    PromptGraphResolver,
    PromptGraphSnapshotRegistry,
    PromptGraphSnapshotService,
    PromptGraphValidator,
    PromptPreviewService,
    RendererPromptCompiler,
    RendererPromptProfileRegistry,
    default_renderer_prompt_profiles,
)
from vscs.application.rendering import (
    ContinuityStateRegistry,
    ManifestDiscoveryResult,
    QualityProfileRegistry,
    RenderAdapterRegistry,
    RendererKind,
    RenderingContracts,
    VoiceProfileRegistry,
    WorkflowCompatibilityValidator,
    WorkflowDiagnosticsFormatter,
    WorkflowManifestLoader,
    WorkflowRegistry,
    default_quality_profiles,
)
from vscs.application.shots import ShotPlanningService
from vscs.application.story import StoryService
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
from vscs.infrastructure.rendering import ComfyUIAdapter, ComfyUIWorkflowCompiler
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
        return self._shutdown

    def create_main_window(self) -> MainWindow:
        from vscs.presentation.story_integration import install_story_browser
        from vscs.presentation.windows.main_window import MainWindow

        install_story_browser()
        return MainWindow(self.services)

    def shutdown(self) -> None:
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
        root = configuration.settings.environment.logs_root.expanduser().resolve(
            strict=False
        )
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
    projects = services.register(
        ProjectService,
        ProjectService(configuration, database),
    )
    stories = services.register(StoryService, StoryService(projects))
    services.register(ShotPlanningService, ShotPlanningService(projects))
    services.register(ACPPEditorService, ACPPEditorService(projects, stories))
    services.register(PromptGraphRegistry, PromptGraphRegistry())
    snapshot_registry = services.register(
        PromptGraphSnapshotRegistry,
        PromptGraphSnapshotRegistry(),
    )
    services.register(
        PromptGraphSnapshotService,
        PromptGraphSnapshotService(snapshot_registry),
    )
    services.register(PromptGraphDiffer, PromptGraphDiffer())
    graph_resolver = services.register(PromptGraphResolver, PromptGraphResolver())
    graph_diagnostics = services.register(
        PromptGraphDiagnosticsFactory,
        PromptGraphDiagnosticsFactory(),
    )
    graph_builder = services.register(
        PromptGraphBuilder,
        PromptGraphBuilder(graph_resolver, graph_diagnostics),
    )
    graph_validator = services.register(PromptGraphValidator, PromptGraphValidator())
    graph_compiler = services.register(
        PromptGraphCompiler,
        PromptGraphCompiler(graph_validator),
    )
    profile_registry = services.register(
        RendererPromptProfileRegistry,
        RendererPromptProfileRegistry(default_renderer_prompt_profiles()),
    )
    renderer_compiler = services.register(
        RendererPromptCompiler,
        RendererPromptCompiler(),
    )
    services.register(PromptPreviewService, PromptPreviewService())
    batch_compiler = services.register(
        BatchPromptCompilationService,
        BatchPromptCompilationService(
            graph_builder,
            graph_compiler,
            profile_registry,
            renderer_compiler,
        ),
    )
    services.register(
        BatchCompilationScheduler,
        BatchCompilationScheduler(batch_compiler),
    )
    services.register(RenderingContracts, RenderingContracts())
    adapter_registry = services.register(RenderAdapterRegistry, RenderAdapterRegistry())
    services.register(
        QualityProfileRegistry,
        QualityProfileRegistry(default_quality_profiles()),
    )
    services.register(ContinuityStateRegistry, ContinuityStateRegistry())
    services.register(VoiceProfileRegistry, VoiceProfileRegistry())
    workflow_registry = services.register(WorkflowRegistry, WorkflowRegistry())
    compatibility = services.register(
        WorkflowCompatibilityValidator,
        WorkflowCompatibilityValidator(),
    )
    services.register(WorkflowDiagnosticsFormatter, WorkflowDiagnosticsFormatter())
    workflow_root = configuration.settings.environment.config_root / "workflows"
    manifest_loader = services.register(
        WorkflowManifestLoader,
        WorkflowManifestLoader(workflow_root / "manifests"),
    )
    services.register(
        ManifestDiscoveryResult,
        manifest_loader.discover(workflow_registry),
    )
    comfyui_adapter = services.register(
        ComfyUIAdapter,
        ComfyUIAdapter(
            workflow_registry,
            compatibility,
            ComfyUIWorkflowCompiler(workflow_root),
        ),
    )
    adapter_registry.register(comfyui_adapter)
    if not adapter_registry.contains(RendererKind.COMFYUI):
        raise RuntimeError("ComfyUI adapter registration failed")

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
                logger.warning(
                    "VSCS environment health check: %s",
                    "; ".join(messages),
                )

    if logger is not None:
        logger.info(
            "VSCS dependency graph initialized in %s mode",
            selected.mode.value,
        )
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
