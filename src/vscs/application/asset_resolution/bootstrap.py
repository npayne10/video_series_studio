"""Dependency registration for Asset Manager resolution services."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.prompt_graph import PromptGraphResolver
from vscs.infrastructure.services import ApplicationServices

from .browser import AssetBrowserService
from .canonical import CanonicalResolutionService
from .prompt_enrichment import PromptGraphAssetEnrichmentService
from .resolver import AssetResolutionService


def register_asset_resolution(services: ApplicationServices) -> AssetResolutionService:
    """Register shared authoritative asset and Prompt Graph services."""
    assets = services.require(AssetService)
    caps = services.require(CAPService)
    references = services.require(CanonicalReferenceService)
    canonical = services.register(
        CanonicalResolutionService,
        CanonicalResolutionService(caps, references),
    )
    resolver = services.register(
        AssetResolutionService,
        AssetResolutionService(assets, caps, references),
    )
    services.register(
        AssetBrowserService,
        AssetBrowserService(assets, resolver, canonical),
    )
    services.register(
        PromptGraphAssetEnrichmentService,
        PromptGraphAssetEnrichmentService(
            resolver,
            canonical,
            services.require(PromptGraphResolver),
        ),
    )
    return resolver
