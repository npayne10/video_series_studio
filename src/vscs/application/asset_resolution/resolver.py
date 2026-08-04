"""Authoritative asset, CAP, and canonical-reference resolution."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.assets import AssetNotFoundError, AssetService
from vscs.application.caps import (
    CAPNotFoundError,
    CAPService,
    CanonicalReferenceService,
)
from vscs.domain.assets import AssetStatus
from vscs.domain.caps import CAPStatus, CanonicalReferenceStatus

from .models import (
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


@dataclass(slots=True)
class AssetResolutionService:
    """Resolve Asset Manager records into immutable production bindings."""

    assets: AssetService
    caps: CAPService
    references: CanonicalReferenceService

    def resolve(self, request: AssetResolutionRequest) -> AssetResolutionResult:
        diagnostics: list[AssetResolutionDiagnostic] = []
        try:
            asset = self.assets.get(request.asset_id)
        except AssetNotFoundError:
            return AssetResolutionResult(
                request,
                AssetResolutionStatus.UNRESOLVED,
                diagnostics=(
                    AssetResolutionDiagnostic(
                        "asset.not_found",
                        AssetResolutionSeverity.ERROR,
                        "Asset is not registered in the active project.",
                        request.asset_id,
                    ),
                ),
            )

        asset_binding = ResolvedAssetBinding(
            asset.asset_id,
            asset.name,
            asset.category,
            asset.description,
            asset.status,
            asset.tags,
            stable_model_checksum(asset),
        )
        if request.expected_category is not None and asset.category is not request.expected_category:
            diagnostics.append(
                AssetResolutionDiagnostic(
                    "asset.category_mismatch",
                    AssetResolutionSeverity.ERROR,
                    "Asset category does not match the requested production role.",
                    asset.asset_id,
                )
            )
        if request.require_approved_asset and asset.status is not AssetStatus.APPROVED:
            diagnostics.append(
                AssetResolutionDiagnostic(
                    "asset.not_approved",
                    AssetResolutionSeverity.ERROR,
                    "Asset is not approved for production use.",
                    asset.asset_id,
                )
            )

        cap_binding: ResolvedCAPBinding | None = None
        cap_found = True
        try:
            cap = self.caps.get(asset.asset_id)
        except CAPNotFoundError:
            cap_found = False
            if request.require_cap:
                diagnostics.append(
                    AssetResolutionDiagnostic(
                        "cap.not_found",
                        AssetResolutionSeverity.ERROR,
                        "Asset has no Canonical Asset Profile.",
                        asset.asset_id,
                    )
                )
        else:
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
                        "Canonical Asset Profile is not approved.",
                        asset.asset_id,
                    )
                )

        reference_bindings: tuple[ResolvedReferenceBinding, ...] = ()
        if cap_found:
            approved = self.references.list_for_cap(
                asset.asset_id,
                status=CanonicalReferenceStatus.APPROVED,
            )
            reference_bindings = tuple(
                ResolvedReferenceBinding(
                    str(reference.id),
                    str(reference.file_path),
                    reference.reference_type.value,
                    reference.role.value,
                    stable_model_checksum(reference),
                )
                for reference in sorted(approved, key=lambda item: item.id)
            )
            if request.require_approved_references and not reference_bindings:
                diagnostics.append(
                    AssetResolutionDiagnostic(
                        "reference.approved_missing",
                        AssetResolutionSeverity.ERROR,
                        "Asset has no approved canonical reference.",
                        asset.asset_id,
                    )
                )

        errors = tuple(
            item for item in diagnostics if item.severity is AssetResolutionSeverity.ERROR
        )
        if not errors:
            status = AssetResolutionStatus.RESOLVED
        elif asset_binding is not None:
            status = AssetResolutionStatus.PARTIAL
        else:
            status = AssetResolutionStatus.UNRESOLVED
        return AssetResolutionResult(
            request,
            status,
            asset_binding,
            cap_binding,
            reference_bindings,
            tuple(diagnostics),
        )

    def resolve_many(
        self,
        requests: tuple[AssetResolutionRequest, ...],
    ) -> tuple[AssetResolutionResult, ...]:
        """Resolve requests in deterministic asset-ID order."""
        return tuple(self.resolve(request) for request in sorted(requests, key=lambda x: x.asset_id))
