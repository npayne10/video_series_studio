"""Dependency registration for Asset Manager resolution services."""

from __future__ import annotations

from vscs.application.assets import AssetService
from vscs.application.caps import CAPService, CanonicalReferenceService
from vscs.infrastructure.services import ApplicationServices

from .resolver import AssetResolutionService


def register_asset_resolution(services: ApplicationServices) -> AssetResolutionService:
    """Register the shared authoritative asset-resolution service."""
    resolver = AssetResolutionService(
        services.require(AssetService),
        services.require(CAPService),
        services.require(CanonicalReferenceService),
    )
    return services.register(AssetResolutionService, resolver)
