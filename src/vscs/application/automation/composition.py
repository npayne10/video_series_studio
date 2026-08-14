"""Composition helpers for governed Phase 19.5 automation services."""

from __future__ import annotations

from vscs.infrastructure.ai import AICredentialStore, OpenAIEpisodeSceneProposalProvider
from vscs.infrastructure.configuration import AIProvider, ConfigurationService
from vscs.infrastructure.services import ApplicationServices

from .episode_scene import (
    EpisodeSceneProposalAutomationService,
    EpisodeSceneProposalProvider,
    TemplateEpisodeSceneProposalProvider,
)
from .service import AutomationProposalService


def register_episode_scene_automation(
    services: ApplicationServices,
) -> EpisodeSceneProposalAutomationService:
    """Register the configured Episode/Scene proposal service exactly once."""
    existing = services.get(EpisodeSceneProposalAutomationService)
    if existing is not None:
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

    service = EpisodeSceneProposalAutomationService(
        provider,
        services.require(AutomationProposalService),
    )
    return services.register(EpisodeSceneProposalAutomationService, service)
