"""Bootstrap helper coverage for asset resolution."""

from vscs.application.asset_resolution import (
    AssetResolutionService,
    register_asset_resolution,
)
from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.infrastructure.services import ApplicationServices


def test_register_asset_resolution_uses_shared_dependencies() -> None:
    services = ApplicationServices()
    assets = object.__new__(AssetService)
    caps = object.__new__(CAPService)
    references = object.__new__(CanonicalReferenceService)
    services.register(AssetService, assets)
    services.register(CAPService, caps)
    services.register(CanonicalReferenceService, references)

    resolver = register_asset_resolution(services)

    assert services.require(AssetResolutionService) is resolver
    assert resolver.assets is assets
    assert resolver.caps is caps
    assert resolver.references is references
