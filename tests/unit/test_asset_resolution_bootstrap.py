"""Bootstrap helper coverage for asset resolution."""

from vscs.application.asset_resolution import (
    AssetResolutionService,
    register_asset_resolution,
)
from vscs.application.assets import AssetService
from vscs.application.caps import CAPService, CanonicalReferenceService
from vscs.infrastructure.services import ApplicationServices


def test_register_asset_resolution_uses_shared_dependencies() -> None:
    services = ApplicationServices()
    assets = object()
    caps = object()
    references = object()
    services.register(AssetService, assets)  # type: ignore[arg-type]
    services.register(CAPService, caps)  # type: ignore[arg-type]
    services.register(CanonicalReferenceService, references)  # type: ignore[arg-type]

    resolver = register_asset_resolution(services)

    assert services.require(AssetResolutionService) is resolver
    assert resolver.assets is assets
    assert resolver.caps is caps
    assert resolver.references is references
