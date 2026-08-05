"""Bootstrap helper coverage for asset resolution."""

from vscs.application.asset_resolution import (
    AssetBrowserService,
    AssetResolutionService,
    CanonicalResolutionService,
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
    canonical = services.require(CanonicalResolutionService)
    browser = services.require(AssetBrowserService)

    assert services.require(AssetResolutionService) is resolver
    assert resolver.assets is assets
    assert resolver.caps is caps
    assert resolver.references is references
    assert canonical.caps is caps
    assert canonical.references is references
    assert browser.assets is assets
    assert browser.resolver is resolver
    assert browser.canonical is canonical
