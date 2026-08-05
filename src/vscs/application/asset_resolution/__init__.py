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
from .prompt_enrichment import (
    PromptAssetDependency,
    PromptAssetEnrichmentRequest,
    PromptAssetEnrichmentResult,
    PromptGraphAssetEnrichmentService,
)
from .propagation import (
    AssetChangePropagationService,
    AssetDependencyChange,
    AssetDependencyChangeKind,
    AssetDependencyIndex,
    AssetPropagationReport,
    ShotAssetDependencyRecord,
)
from .resolver import AssetResolutionService

__all__ = [
    "AssetBrowserFilter",
    "AssetBrowserItem",
    "AssetBrowserResult",
    "AssetBrowserService",
    "AssetChangePropagationService",
    "AssetDependencyChange",
    "AssetDependencyChangeKind",
    "AssetDependencyFingerprint",
    "AssetDependencyIndex",
    "AssetPropagationReport",
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
    "PromptAssetDependency",
    "PromptAssetEnrichmentRequest",
    "PromptAssetEnrichmentResult",
    "PromptGraphAssetEnrichmentService",
    "ResolvedAssetBinding",
    "ResolvedCAPBinding",
    "ResolvedReferenceBinding",
    "ShotAssetDependencyRecord",
    "register_asset_resolution",
    "stable_model_checksum",
]
