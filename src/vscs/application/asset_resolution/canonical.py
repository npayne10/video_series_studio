"""Dedicated CAP and canonical-reference production resolution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from vscs.application.caps import (
    CanonicalReferenceService,
    CAPNotFoundError,
    CAPService,
)
from vscs.domain.caps import (
    CanonicalReference,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CAPStatus,
)

from .models import (
    AssetResolutionDiagnostic,
    AssetResolutionSeverity,
    ResolvedCAPBinding,
    canonical_reference_file_checksum,
    stable_model_checksum,
)


class CanonicalResolutionStatus(StrEnum):
    """Production readiness of one CAP and its canonical references."""

    READY = "ready"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class CanonicalResolutionRequest:
    """Resolve canonical production truth for one asset."""

    asset_id: str
    require_approved_cap: bool = True
    require_primary_reference: bool = True
    minimum_approved_references: int = 1
    reference_types: frozenset[CanonicalReferenceType] = frozenset()
    reference_roles: frozenset[CanonicalReferenceRole] = frozenset()

    def __post_init__(self) -> None:
        normalized = self.asset_id.strip().upper()
        if not normalized:
            raise ValueError("asset_id is required")
        if self.minimum_approved_references < 0:
            raise ValueError("minimum_approved_references cannot be negative")
        object.__setattr__(self, "asset_id", normalized)


@dataclass(frozen=True, slots=True)
class CanonicalReferenceBinding:
    """Approved immutable reference with separate authority and file identities."""

    reference_id: str
    title: str
    file_path: str
    reference_type: CanonicalReferenceType
    role: CanonicalReferenceRole
    version: str
    description: str
    notes: str
    reference_fingerprint: str
    file_checksum: str = ""

    @property
    def checksum(self) -> str:
        """Backward-compatible alias for the reference metadata fingerprint."""
        return self.reference_fingerprint


@dataclass(frozen=True, slots=True)
class CanonicalDependencyFingerprint:
    """Combined checksum for a CAP and its selected reference authority."""

    asset_id: str
    cap_checksum: str
    reference_checksums: tuple[str, ...]

    @property
    def checksum(self) -> str:
        payload = {
            "asset_id": self.asset_id,
            "cap_checksum": self.cap_checksum,
            "reference_checksums": list(self.reference_checksums),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class CanonicalResolutionResult:
    """Complete CAP and canonical-reference resolution outcome."""

    request: CanonicalResolutionRequest
    status: CanonicalResolutionStatus
    cap: ResolvedCAPBinding | None = None
    references: tuple[CanonicalReferenceBinding, ...] = ()
    primary_reference: CanonicalReferenceBinding | None = None
    diagnostics: tuple[AssetResolutionDiagnostic, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status is CanonicalResolutionStatus.READY

    @property
    def fingerprint(self) -> CanonicalDependencyFingerprint | None:
        if self.cap is None:
            return None
        return CanonicalDependencyFingerprint(
            self.request.asset_id,
            self.cap.checksum,
            tuple(reference.reference_fingerprint for reference in self.references),
        )


@dataclass(slots=True)
class CanonicalResolutionService:
    """Resolve approved CAP data and canonical reference selections."""

    caps: CAPService
    references: CanonicalReferenceService

    def resolve(self, request: CanonicalResolutionRequest) -> CanonicalResolutionResult:
        diagnostics: list[AssetResolutionDiagnostic] = []
        try:
            cap = self.caps.get(request.asset_id)
        except CAPNotFoundError:
            return CanonicalResolutionResult(
                request,
                CanonicalResolutionStatus.UNRESOLVED,
                diagnostics=(
                    AssetResolutionDiagnostic(
                        "cap.not_found",
                        AssetResolutionSeverity.ERROR,
                        "Asset has no Canonical Asset Profile.",
                        request.asset_id,
                    ),
                ),
            )

        cap_binding = ResolvedCAPBinding(
            cap.asset_id,
            cap.title,
            cap.version,
            cap.status,
            cap.canonical_description,
            cap.visual_identity,
            cap.production_notes,
            stable_model_checksum(cap),
        )
        if request.require_approved_cap and cap.status is not CAPStatus.APPROVED:
            diagnostics.append(
                AssetResolutionDiagnostic(
                    "cap.not_approved",
                    AssetResolutionSeverity.ERROR,
                    "Canonical Asset Profile is not approved for production.",
                    cap.asset_id,
                )
            )

        approved = self.references.list_for_cap(
            cap.asset_id,
            status=CanonicalReferenceStatus.APPROVED,
        )
        selected = tuple(
            reference
            for reference in approved
            if (not request.reference_types or reference.reference_type in request.reference_types)
            and (not request.reference_roles or reference.role in request.reference_roles)
        )
        ordered = tuple(
            sorted(
                selected,
                key=lambda reference: (
                    self._role_priority(reference.role),
                    reference.reference_type.value,
                    reference.id,
                ),
            )
        )
        bindings = tuple(self._binding(reference) for reference in ordered)
        primaries = tuple(
            reference for reference in bindings if reference.role is CanonicalReferenceRole.PRIMARY
        )
        primary = primaries[0] if primaries else None

        if len(bindings) < request.minimum_approved_references:
            diagnostics.append(
                AssetResolutionDiagnostic(
                    "reference.minimum_not_met",
                    AssetResolutionSeverity.ERROR,
                    "The minimum number of approved canonical references is not met.",
                    cap.asset_id,
                )
            )
        if request.require_primary_reference and primary is None:
            diagnostics.append(
                AssetResolutionDiagnostic(
                    "reference.primary_missing",
                    AssetResolutionSeverity.ERROR,
                    "No approved primary canonical reference is available.",
                    cap.asset_id,
                )
            )
        if len(primaries) > 1:
            diagnostics.append(
                AssetResolutionDiagnostic(
                    "reference.multiple_primaries",
                    AssetResolutionSeverity.WARNING,
                    "Multiple approved primary references exist; "
                    "the first stable match was selected.",
                    cap.asset_id,
                )
            )

        has_errors = any(
            diagnostic.severity is AssetResolutionSeverity.ERROR for diagnostic in diagnostics
        )
        status = (
            CanonicalResolutionStatus.PARTIAL if has_errors else CanonicalResolutionStatus.READY
        )
        return CanonicalResolutionResult(
            request,
            status,
            cap_binding,
            bindings,
            primary,
            tuple(diagnostics),
        )

    def _binding(self, reference: CanonicalReference) -> CanonicalReferenceBinding:
        project_directory = None
        try:
            project_directory = self.caps.assets.projects.project_directory
        except AttributeError:
            # Canonical metadata resolution must remain usable with lightweight
            # service implementations that do not expose the desktop project graph.
            # Physical integrity is optional here and enforced again when a provider-
            # ready package has an actual project directory and canonical file.
            pass
        return CanonicalReferenceBinding(
            str(reference.id),
            reference.title,
            str(reference.file_path),
            reference.reference_type,
            reference.role,
            reference.version,
            reference.description,
            reference.notes,
            stable_model_checksum(reference),
            canonical_reference_file_checksum(project_directory, reference.file_path),
        )

    @staticmethod
    def _role_priority(role: CanonicalReferenceRole) -> int:
        return {
            CanonicalReferenceRole.PRIMARY: 0,
            CanonicalReferenceRole.SECONDARY: 1,
            CanonicalReferenceRole.SUPPLEMENTARY: 2,
        }[role]
