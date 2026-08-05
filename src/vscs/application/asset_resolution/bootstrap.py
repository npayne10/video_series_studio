"""Dependency registration for Asset Manager resolution services."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.infrastructure.services import ApplicationServices

from .browser import AssetBrowserService
from .resolver import AssetResolutionService


def register_asset_resolution(services: ApplicationServices) -> AssetResolutionService:
    """Register shared authoritative resolution and browsing services."""
    assets = services.require(AssetService)
    resolver = AssetResolutionService(
        assets,
        services.require(CAPService),
        services.require(CanonicalReferenceService),
    )
    registered = services.register(AssetResolutionService, resolver)
    services.register(AssetBrowserService, AssetBrowserService(assets, registered))
    return registered
