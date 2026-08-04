"""Workflow manifest contracts, discovery, compatibility, and registry."""

from .compatibility import (
    InstalledWorkflowResources,
    WorkflowCompatibilityValidator,
)
from .diagnostics import (
    CompatibilityDiagnostic,
    CompatibilitySeverity,
    WorkflowCompatibilityReport,
)
from .loader import (
    ManifestDiagnostic,
    ManifestDiagnosticLevel,
    ManifestDiscoveryResult,
    WorkflowManifestLoader,
)
from .manifest import (
    WorkflowInputKind,
    WorkflowManifest,
    WorkflowMetadata,
    WorkflowNodeBinding,
    WorkflowNodeSelector,
    WorkflowRequirement,
    WorkflowRequirementKind,
    workflow_manifest_schema,
)
from .registry import (
    DuplicateWorkflowManifestError,
    WorkflowManifestRegistryError,
    WorkflowRegistry,
)

__all__ = [
    "CompatibilityDiagnostic",
    "CompatibilitySeverity",
    "DuplicateWorkflowManifestError",
    "InstalledWorkflowResources",
    "ManifestDiagnostic",
    "ManifestDiagnosticLevel",
    "ManifestDiscoveryResult",
    "WorkflowCompatibilityReport",
    "WorkflowCompatibilityValidator",
    "WorkflowInputKind",
    "WorkflowManifest",
    "WorkflowManifestLoader",
    "WorkflowManifestRegistryError",
    "WorkflowMetadata",
    "WorkflowNodeBinding",
    "WorkflowNodeSelector",
    "WorkflowRegistry",
    "WorkflowRequirement",
    "WorkflowRequirementKind",
    "workflow_manifest_schema",
]
