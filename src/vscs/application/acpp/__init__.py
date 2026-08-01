"""Advanced Clip Production Package public API."""

from .builder import ACPPBuildError, ClipProductionPackageBuilder
from .catalogs import CAPAssetResolutionCatalog, FilesystemBehaviourResolutionCatalog
from .compiler import ACPPCompilationError, ACPPCompilerConfig, SSIEToACPPCompiler
from .identifiers import build_clip_id
from .models import (
    AssetBinding,
    AssetBindingRole,
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderQualityMode,
    RenderSpecification,
    SeedPolicy,
)
from .protocols import ClipPackageSerializer, ClipPackageValidator
from .resolution import (
    ACPPResolutionResult,
    ACPPResolverConfig,
    AssetResolutionCatalog,
    AssetResolutionRecord,
    BehaviourResolutionCatalog,
    BehaviourResolutionRecord,
    CanonicalReferenceResolution,
    ResolutionDiagnostic,
    ResolutionProvenance,
    ResolutionSeverity,
)
from .resolver import ACPPResolutionError, ACPPResourceResolver
from .serialization import ACPPSerializationError, ACPPSerializer
from .validator import (
    ACPPValidationIssue,
    ACPPValidationResult,
    ACPPValidationSeverity,
    ACPPValidator,
)

__all__ = [
    "ACPPBuildError",
    "ACPPCompilationError",
    "ACPPCompilerConfig",
    "ACPPResolutionError",
    "ACPPResolutionResult",
    "ACPPResolverConfig",
    "ACPPResourceResolver",
    "ACPPSerializationError",
    "ACPPSerializer",
    "ACPPValidationIssue",
    "ACPPValidationResult",
    "ACPPValidationSeverity",
    "ACPPValidator",
    "AssetBinding",
    "AssetBindingRole",
    "AssetResolutionCatalog",
    "AssetResolutionRecord",
    "AudioSpecification",
    "BehaviourResolutionCatalog",
    "BehaviourResolutionRecord",
    "CAPAssetResolutionCatalog",
    "CanonicalReferenceResolution",
    "ClipIdentity",
    "ClipPackageSerializer",
    "ClipPackageValidator",
    "ClipProductionPackage",
    "ClipProductionPackageBuilder",
    "ContinuityBinding",
    "FilesystemBehaviourResolutionCatalog",
    "OutputSpecification",
    "PromptSpecification",
    "RenderQualityMode",
    "RenderSpecification",
    "ResolutionDiagnostic",
    "ResolutionProvenance",
    "ResolutionSeverity",
    "SSIEToACPPCompiler",
    "SeedPolicy",
    "build_clip_id",
]
