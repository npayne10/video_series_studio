"""Late composition of AI Story Analysis after project asset services are available."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.story_analysis.ai_analysis import (
    AssetServiceStoryEntityCatalog,
    EntityResolutionService,
)
from vscs.application.story_analysis.registry import StoryAnalysisStageRegistry
from vscs.application.story_analysis.stages import AIStoryAnalysisStage
from vscs.infrastructure.ai import (
    AICredentialStore,
    OpenAIStoryAIAnalysisProvider,
    TemplateStoryAIAnalysisProvider,
)
from vscs.infrastructure.configuration import AIProvider, ConfigurationService
from vscs.infrastructure.services import ApplicationServices


def register_ai_story_analysis(services: ApplicationServices) -> EntityResolutionService:
    """Attach the configured AI enrichment stage exactly once."""

    existing = services.get(EntityResolutionService)
    if existing is not None:
        return existing
    configuration = services.require(ConfigurationService)
    provider = TemplateStoryAIAnalysisProvider()
    if configuration.settings.ai.provider is AIProvider.OPENAI:
        try:
            provider = OpenAIStoryAIAnalysisProvider(
                api_key=AICredentialStore().get_openai_api_key(),
                model=configuration.settings.ai.openai_model,
            )
        except (RuntimeError, ValueError):
            provider = TemplateStoryAIAnalysisProvider()
    catalog = AssetServiceStoryEntityCatalog(services.require(AssetService))
    resolution = EntityResolutionService(provider, catalog)
    services.register(EntityResolutionService, resolution)
    registry = services.require(StoryAnalysisStageRegistry)
    if not registry.contains(AIStoryAnalysisStage.stage_id):
        registry.register(AIStoryAnalysisStage(resolution))
    return resolution
