"""Asset Manager resolution contracts and services."""

from .bootstrap import register_asset_resolution
from .browser import (
    AssetBrowserFilter,
    AssetBrowserItem,
    AssetBrowserResult,
    AssetBrowserService,
)
from .models import (
    AssetDependencyFingerprint,
    AssetResolutionDiagnostic,
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionSeverity,
    AssetResolutionStatus,
    ResolvedAssetBinding,
    ResolvedCAPBinding,
    ResolvedReferenceBinding,
    stable_model_checksum,
)
from .resolver import AssetResolutionService

__all__ = [
    "AssetBrowserFilter",
    "AssetBrowserItem",
    "AssetBrowserResult",
    "AssetBrowserService",
    "AssetDependencyFingerprint",
    "AssetResolutionDiagnostic",
    "AssetResolutionRequest",
    "AssetResolutionResult",
    "AssetResolutionService",
    "AssetResolutionSeverity",
    "AssetResolutionStatus",
    "ResolvedAssetBinding",
    "ResolvedCAPBinding",
    "ResolvedReferenceBinding",
    "register_asset_resolution",
    "stable_model_checksum",
]
