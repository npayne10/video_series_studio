"""Resolution contracts and results for ACPP production resources."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from .models import ClipProductionPackage


class ResolutionSeverity(StrEnum):
    """Severity assigned to one production-resource resolution finding."""

    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True, slots=True)
class CanonicalReferenceResolution:
    """Approved canonical reference exposed by an asset catalog."""

    reference_id: str
    path: str
    role: str = "secondary"
    reference_type: str = "image"
    approved: bool = True
    locked: bool = True
    checksum: str | None = None


@dataclass(frozen=True, slots=True)
class AssetResolutionRecord:
    """Resolved CAP and canonical-reference state for one asset."""

    asset_id: str
    cap_id: str
    cap_version: str
    cap_approved: bool
    canonical_references: tuple[CanonicalReferenceResolution, ...] = ()
    camera_profile_ids: tuple[str, ...] = ()
    lighting_profile_ids: tuple[str, ...] = ()
    audio_profile_ids: tuple[str, ...] = ()
    checksum: str | None = None


@dataclass(frozen=True, slots=True)
class BehaviourResolutionRecord:
    """Resolved behaviour or prompt package state."""

    package_id: str
    version: str
    structurally_valid: bool
    manifest_path: str
    prompt_package_ids: tuple[str, ...] = ()
    dependency_ids: tuple[str, ...] = ()
    checksum: str | None = None


class AssetResolutionCatalog(Protocol):
    """Look up approved CAP and canonical-reference state."""

    def resolve_asset(self, asset_id: str) -> AssetResolutionRecord | None:
        """Return the resolution record for an asset, if available."""
        ...


class BehaviourResolutionCatalog(Protocol):
    """Look up behaviour and prompt package state."""

    def resolve_behaviour(self, package_id: str) -> BehaviourResolutionRecord | None:
        """Return the resolution record for a behaviour package, if available."""
        ...


@dataclass(frozen=True, slots=True)
class ResolutionDiagnostic:
    """One machine-readable production-resource resolution finding."""

    severity: ResolutionSeverity
    code: str
    message: str
    resource_id: str


@dataclass(frozen=True, slots=True)
class ResolutionProvenance:
    """Provenance captured for one successfully resolved resource."""

    resource_id: str
    resource_type: str
    version: str
    source: str
    checksum: str | None = None
    related_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ACPPResolutionResult:
    """Resolved package plus diagnostics and provenance."""

    package: ClipProductionPackage
    diagnostics: tuple[ResolutionDiagnostic, ...] = ()
    provenance: tuple[ResolutionProvenance, ...] = ()
    resolved_dependencies: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Return whether no error-level diagnostics were emitted."""
        return not any(
            diagnostic.severity is ResolutionSeverity.ERROR
            for diagnostic in self.diagnostics
        )


@dataclass(frozen=True, slots=True)
class ACPPResolverConfig:
    """Policy controlling resource resolution strictness."""

    require_approved_caps: bool = True
    require_approved_references: bool = True
    require_primary_reference: bool = True
    require_valid_behaviours: bool = True
    include_secondary_references: bool = True
    metadata_prefix: str = "resolution"

    def __post_init__(self) -> None:
        if not self.metadata_prefix.strip():
            raise ValueError("metadata_prefix must not be empty")
