"""Advanced Clip Production Package public API."""

from .builder import ACPPBuildError, ClipProductionPackageBuilder
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
    "ACPPSerializationError",
    "ACPPSerializer",
    "ACPPValidationIssue",
    "ACPPValidationResult",
    "ACPPValidationSeverity",
    "ACPPValidator",
    "AssetBinding",
    "AssetBindingRole",
    "AudioSpecification",
    "ClipIdentity",
    "ClipPackageSerializer",
    "ClipPackageValidator",
    "ClipProductionPackage",
    "ClipProductionPackageBuilder",
    "ContinuityBinding",
    "OutputSpecification",
    "PromptSpecification",
    "RenderQualityMode",
    "RenderSpecification",
    "SSIEToACPPCompiler",
    "SeedPolicy",
    "build_clip_id",
]
