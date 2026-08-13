"""Bootstrap helper coverage for asset resolution."""

from vscs.application.asset_resolution import (
    AssetBrowserService,
    AssetChangePropagationService,
    AssetDependencyIndex,
    AssetResolutionService,
    CanonicalResolutionService,
    PromptGraphAssetEnrichmentService,
    register_asset_resolution,
)
from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.prompt_graph import (
    IncrementalCompilationHistory,
    PromptGraphResolver,
)
from vscs.infrastructure.services import ApplicationServices


def test_register_asset_resolution_uses_shared_dependencies() -> None:
    services = ApplicationServices()
    assets = object.__new__(AssetService)
    caps = object.__new__(CAPService)
    references = object.__new__(CanonicalReferenceService)
    graph_resolver = services.register(PromptGraphResolver, PromptGraphResolver())
    history = services.register(
        IncrementalCompilationHistory,
        IncrementalCompilationHistory(),
    )
    services.register(AssetService, assets)
    services.register(CAPService, caps)
    services.register(CanonicalReferenceService, references)

    resolver = register_asset_resolution(services)
    canonical = services.require(CanonicalResolutionService)
    browser = services.require(AssetBrowserService)
    enrichment = services.require(PromptGraphAssetEnrichmentService)
    index = services.require(AssetDependencyIndex)
    propagation = services.require(AssetChangePropagationService)

    assert services.require(AssetResolutionService) is resolver
    assert resolver.assets is assets
    assert resolver.caps is caps
    assert resolver.references is references
    assert resolver.production_projections is not None
    assert resolver.production_projections.caps is caps
    assert resolver.production_projections.references is references
    assert canonical.caps is caps
    assert canonical.references is references
    assert browser.assets is assets
    assert browser.resolver is resolver
    assert browser.canonical is canonical
    assert enrichment.assets is resolver
    assert enrichment.canonical is canonical
    assert enrichment.resolver is graph_resolver
    assert propagation.index is index
    assert propagation.enrichment is enrichment
    assert propagation.compilation_history is history
