"""Enrich Prompt Graph sources with authoritative asset production truth."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.prompt_graph import (
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.domain.assets import AssetCategory

from .canonical import CanonicalResolutionRequest, CanonicalResolutionService
from .models import (
    AssetResolutionDiagnostic,
    AssetResolutionRequest,
    AssetResolutionSeverity,
)
from .resolver import AssetResolutionService


@dataclass(frozen=True, slots=True)
class PromptAssetEnrichmentRequest:
    """Request canonical Prompt Graph contributions for selected assets."""

    shot_id: str
    asset_ids: tuple[str, ...]
    mandatory: bool = True

    def __post_init__(self) -> None:
        shot_id = self.shot_id.strip()
        normalized_ids = (
            asset_id.strip().upper()
            for asset_id in self.asset_ids
            if asset_id.strip()
        )
        asset_ids = tuple(dict.fromkeys(normalized_ids))
        if not shot_id:
            raise ValueError("shot_id is required")
        if not asset_ids:
            raise ValueError("at least one asset_id is required")
        object.__setattr__(self, "shot_id", shot_id)
        object.__setattr__(self, "asset_ids", asset_ids)


@dataclass(frozen=True, slots=True)
class PromptAssetDependency:
    """Dependency checksum contributed by one resolved production asset."""

    asset_id: str
    asset_checksum: str
    cap_checksum: str
    reference_checksums: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PromptAssetEnrichmentResult:
    """Complete enrichment outcome for one shot."""

    request: PromptAssetEnrichmentRequest
    sources: tuple[PromptGraphSource, ...]
    canonical_asset_ids: tuple[str, ...]
    reference_ids: tuple[str, ...]
    dependencies: tuple[PromptAssetDependency, ...]
    diagnostics: tuple[AssetResolutionDiagnostic, ...] = ()

    @property
    def ready(self) -> bool:
        return not any(
            diagnostic.severity is AssetResolutionSeverity.ERROR
            for diagnostic in self.diagnostics
        )


@dataclass(slots=True)
class PromptGraphAssetEnrichmentService:
    """Translate resolved assets into deterministic Prompt Graph sources."""

    assets: AssetResolutionService
    canonical: CanonicalResolutionService
    resolver: PromptGraphResolver

    def enrich(
        self,
        request: PromptAssetEnrichmentRequest,
    ) -> PromptAssetEnrichmentResult:
        sources: list[PromptGraphSource] = []
        canonical_asset_ids: list[str] = []
        reference_ids: list[str] = []
        dependencies: list[PromptAssetDependency] = []
        diagnostics: list[AssetResolutionDiagnostic] = []

        for sequence, asset_id in enumerate(sorted(request.asset_ids), start=100):
            resolution = self.assets.resolve(AssetResolutionRequest(asset_id))
            canonical = self.canonical.resolve(CanonicalResolutionRequest(asset_id))
            diagnostics.extend(resolution.diagnostics)
            diagnostics.extend(canonical.diagnostics)
            if resolution.asset is None or resolution.cap is None:
                continue

            references = tuple(
                reference.reference_id for reference in canonical.references
            )
            content = self._content(
                resolution.cap.canonical_description,
                resolution.cap.visual_identity,
                resolution.cap.production_notes,
            )
            primary_reference_id = (
                canonical.primary_reference.reference_id
                if canonical.primary_reference is not None
                else ""
            )
            attributes = (
                ("asset_category", resolution.asset.category.value),
                ("asset_checksum", resolution.asset.checksum),
                ("cap_checksum", resolution.cap.checksum),
                ("cap_version", resolution.cap.version),
                ("canonical_status", canonical.status.value),
                ("primary_reference_id", primary_reference_id),
            )
            sources.append(
                PromptGraphSource(
                    source_id=f"asset:{asset_id}",
                    kind=self._node_kind(resolution.asset.category),
                    label=resolution.asset.name,
                    content=content,
                    canonical_asset_id=asset_id,
                    reference_ids=references,
                    attributes=attributes,
                    mandatory=request.mandatory,
                    sequence=sequence,
                )
            )
            canonical_asset_ids.append(asset_id)
            reference_ids.extend(references)
            dependencies.append(
                PromptAssetDependency(
                    asset_id,
                    resolution.asset.checksum,
                    resolution.cap.checksum,
                    tuple(
                        reference.checksum for reference in canonical.references
                    ),
                )
            )

        result = PromptAssetEnrichmentResult(
            request,
            tuple(sources),
            tuple(canonical_asset_ids),
            tuple(dict.fromkeys(reference_ids)),
            tuple(dependencies),
            tuple(diagnostics),
        )
        self.resolver.extend(request.shot_id, result.sources)
        return result

    @staticmethod
    def _content(description: str, visual_identity: str, notes: str) -> str:
        parts = (description, visual_identity, notes)
        return " ".join(part.strip() for part in parts if part.strip())

    @staticmethod
    def _node_kind(category: AssetCategory) -> PromptNodeKind:
        return {
            AssetCategory.CHARACTER: PromptNodeKind.CHARACTER,
            AssetCategory.SHIP: PromptNodeKind.SHIP,
            AssetCategory.VEHICLE: PromptNodeKind.VEHICLE,
            AssetCategory.LOCATION: PromptNodeKind.LOCATION,
            AssetCategory.ENVIRONMENT: PromptNodeKind.ENVIRONMENT,
            AssetCategory.PROP: PromptNodeKind.PROP,
            AssetCategory.EFFECT: PromptNodeKind.EFFECT,
            AssetCategory.AUDIO: PromptNodeKind.AUDIO,
            AssetCategory.CAMERA: PromptNodeKind.CAMERA,
            AssetCategory.LIGHTING: PromptNodeKind.LIGHTING,
        }.get(category, PromptNodeKind.OTHER)
