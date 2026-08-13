"""Dependency registration for Asset Manager resolution services."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.caps import (
    CanonicalReferenceService,
    CAPService,
    ProductionProjectionService,
)
from vscs.application.prompt_graph import (
    IncrementalCompilationHistory,
    PromptGraphResolver,
)
from vscs.infrastructure.services import ApplicationServices

from .browser import AssetBrowserService
from .canonical import CanonicalResolutionService
from .prompt_enrichment import PromptGraphAssetEnrichmentService
from .propagation import AssetChangePropagationService, AssetDependencyIndex
from .resolver import AssetResolutionService


def register_asset_resolution(services: ApplicationServices) -> AssetResolutionService:
    """Register shared authoritative asset and Prompt Graph services."""
    assets = services.require(AssetService)
    caps = services.require(CAPService)
    references = services.require(CanonicalReferenceService)
    production_projections = ProductionProjectionService(caps, references)
    canonical = services.register(
        CanonicalResolutionService,
        CanonicalResolutionService(caps, references),
    )
    resolver = services.register(
        AssetResolutionService,
        AssetResolutionService(assets, caps, references, production_projections),
    )
    services.register(
        AssetBrowserService,
        AssetBrowserService(assets, resolver, canonical),
    )
    enrichment = services.register(
        PromptGraphAssetEnrichmentService,
        PromptGraphAssetEnrichmentService(
            resolver,
            canonical,
            services.require(PromptGraphResolver),
        ),
    )
    dependency_index = services.register(
        AssetDependencyIndex,
        AssetDependencyIndex(),
    )
    services.register(
        AssetChangePropagationService,
        AssetChangePropagationService(
            dependency_index,
            enrichment,
            services.require(IncrementalCompilationHistory),
        ),
    )
    return resolver
