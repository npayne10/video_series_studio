"""Asset Manager resolution contracts and services."""

from .bootstrap import register_asset_resolution
from .browser import (
    AssetBrowserFilter,
    AssetBrowserItem,
    AssetBrowserResult,
    AssetBrowserService,
)
from .canonical import (
    CanonicalDependencyFingerprint,
    CanonicalReferenceBinding,
    CanonicalResolutionRequest,
    CanonicalResolutionResult,
    CanonicalResolutionService,
    CanonicalResolutionStatus,
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
    "CanonicalDependencyFingerprint",
    "CanonicalReferenceBinding",
    "CanonicalResolutionRequest",
    "CanonicalResolutionResult",
    "CanonicalResolutionService",
    "CanonicalResolutionStatus",
    "ResolvedAssetBinding",
    "ResolvedCAPBinding",
    "ResolvedReferenceBinding",
    "register_asset_resolution",
    "stable_model_checksum",
]
