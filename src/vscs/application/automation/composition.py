"""Composition helpers for governed Phase 19.5 automation services."""

from __future__ import annotations

from vscs.application.asset_resolution import AssetResolutionService, register_asset_resolution
from vscs.application.assets import AssetService
from vscs.application.story_analysis.ai_analysis import AssetServiceStoryEntityCatalog
from vscs.infrastructure.ai import AICredentialStore
from vscs.infrastructure.ai.action_performance_provider import (
    OpenAIActionPerformanceProposalProvider,
)
from vscs.infrastructure.ai.environment_provider import OpenAIEnvironmentProposalProvider
from vscs.infrastructure.ai.episode_scene_provider import OpenAIEpisodeSceneProposalProvider
from vscs.infrastructure.ai.scene_shot_provider import OpenAISceneShotProposalProvider
from vscs.infrastructure.configuration import AIProvider, ConfigurationService
from vscs.infrastructure.services import ApplicationServices

from .action_performance import (
    ActionPerformanceProposalAutomationService,
    ActionPerformanceProposalProvider,
    TemplateActionPerformanceProposalProvider,
)
from .canonical_entity import CanonicalEntityAssetResolutionAutomationService
from .environment import (
    EnvironmentProposalAutomationService,
    EnvironmentProposalProvider,
    TemplateEnvironmentProposalProvider,
)
from .episode_scene import (
    EpisodeSceneProposalAutomationService,
    EpisodeSceneProposalProvider,
    TemplateEpisodeSceneProposalProvider,
)
from .scene_shot import (
    SceneShotProposalAutomationService,
    SceneShotProposalProvider,
    TemplateSceneShotProposalProvider,
)
from .service import AutomationProposalService


def register_episode_scene_automation(
    services: ApplicationServices,
) -> EpisodeSceneProposalAutomationService:
    existing = services.get(EpisodeSceneProposalAutomationService)
    if existing is not None:
        register_scene_shot_automation(services)
        return existing
    configuration = services.require(ConfigurationService)
    provider: EpisodeSceneProposalProvider = TemplateEpisodeSceneProposalProvider()
    if configuration.settings.ai.provider is AIProvider.OPENAI:
        try:
            provider = OpenAIEpisodeSceneProposalProvider(
                api_key=AICredentialStore().get_openai_api_key(),
                model=configuration.settings.ai.openai_model,
            )
        except (RuntimeError, ValueError):
            provider = TemplateEpisodeSceneProposalProvider()
    registered = services.register(
        EpisodeSceneProposalAutomationService,
        EpisodeSceneProposalAutomationService(
            provider, services.require(AutomationProposalService)
        ),
    )
    register_scene_shot_automation(services)
    return registered


def register_scene_shot_automation(
    services: ApplicationServices,
) -> SceneShotProposalAutomationService:
    existing = services.get(SceneShotProposalAutomationService)
    if existing is not None:
        register_canonical_entity_asset_automation(services)
        return existing
    configuration = services.require(ConfigurationService)
    provider: SceneShotProposalProvider = TemplateSceneShotProposalProvider()
    if configuration.settings.ai.provider is AIProvider.OPENAI:
        try:
            provider = OpenAISceneShotProposalProvider(
                api_key=AICredentialStore().get_openai_api_key(),
                model=configuration.settings.ai.openai_model,
            )
        except (RuntimeError, ValueError):
            provider = TemplateSceneShotProposalProvider()
    registered = services.register(
        SceneShotProposalAutomationService,
        SceneShotProposalAutomationService(provider, services.require(AutomationProposalService)),
    )
    register_canonical_entity_asset_automation(services)
    return registered


def register_canonical_entity_asset_automation(
    services: ApplicationServices,
) -> CanonicalEntityAssetResolutionAutomationService:
    existing = services.get(CanonicalEntityAssetResolutionAutomationService)
    if existing is not None:
        register_action_performance_automation(services)
        return existing
    resolver = services.get(AssetResolutionService)
    if resolver is None:
        resolver = register_asset_resolution(services)
    service = CanonicalEntityAssetResolutionAutomationService(
        resolver,
        services.require(AutomationProposalService),
        AssetServiceStoryEntityCatalog(services.require(AssetService)),
    )
    registered = services.register(CanonicalEntityAssetResolutionAutomationService, service)
    register_action_performance_automation(services)
    return registered


def register_action_performance_automation(
    services: ApplicationServices,
) -> ActionPerformanceProposalAutomationService:
    """Register proposal-only Phase 19.5.6 automation exactly once."""
    existing = services.get(ActionPerformanceProposalAutomationService)
    if existing is not None:
        register_environment_automation(services)
        return existing
    configuration = services.require(ConfigurationService)
    provider: ActionPerformanceProposalProvider = TemplateActionPerformanceProposalProvider()
    if configuration.settings.ai.provider is AIProvider.OPENAI:
        try:
            provider = OpenAIActionPerformanceProposalProvider(
                api_key=AICredentialStore().get_openai_api_key(),
                model=configuration.settings.ai.openai_model,
            )
        except (RuntimeError, ValueError):
            provider = TemplateActionPerformanceProposalProvider()
    registered = services.register(
        ActionPerformanceProposalAutomationService,
        ActionPerformanceProposalAutomationService(
            provider, services.require(AutomationProposalService)
        ),
    )
    register_environment_automation(services)
    return registered


def register_environment_automation(
    services: ApplicationServices,
) -> EnvironmentProposalAutomationService:
    """Register proposal-only Phase 19.5.7 Environment automation exactly once."""
    existing = services.get(EnvironmentProposalAutomationService)
    if existing is not None:
        return existing
    configuration = services.require(ConfigurationService)
    provider: EnvironmentProposalProvider = TemplateEnvironmentProposalProvider()
    if configuration.settings.ai.provider is AIProvider.OPENAI:
        try:
            provider = OpenAIEnvironmentProposalProvider(
                api_key=AICredentialStore().get_openai_api_key(),
                model=configuration.settings.ai.openai_model,
            )
        except (RuntimeError, ValueError):
            provider = TemplateEnvironmentProposalProvider()
    return services.register(
        EnvironmentProposalAutomationService,
        EnvironmentProposalAutomationService(provider, services.require(AutomationProposalService)),
    )
