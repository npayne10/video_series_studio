"""Application API for stable CAP production projections."""

from __future__ import annotations

from vscs.application.caps.readiness_service import CAPReadinessService
from vscs.application.caps.reference_library import ReferenceLibraryService
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.service import CAPService
from vscs.domain.caps.production_contract import (
    CanonicalIdentity,
    CanonicalReferenceLifecycle,
)
from vscs.domain.caps.production_projection import ProductionProjection
from vscs.domain.caps.structured_knowledge import is_production_authority


class ProductionProjectionError(RuntimeError):
    """Base error for production projection publication."""


class ProductionProjectionBlockedError(ProductionProjectionError):
    """Raised when a production-ready projection is requested for a blocked CAP."""

    def __init__(self, projection: ProductionProjection) -> None:
        self.projection = projection
        messages = "; ".join(gap.message for gap in projection.readiness.blocking_gaps)
        detail = messages or "Production Readiness is not Ready"
        super().__init__(f"{projection.identity.asset_id} is not production ready: {detail}")


class ProductionProjectionService:
    """Publish repository-independent canonical asset projections."""

    def __init__(
        self,
        caps: CAPService,
        references: CanonicalReferenceService,
        library: ReferenceLibraryService | None = None,
        readiness: CAPReadinessService | None = None,
    ) -> None:
        self.caps = caps
        self.references = references
        self.library = library or ReferenceLibraryService(references)
        self.readiness = readiness or CAPReadinessService(caps, references, self.library)

    def project(self, asset_id: str) -> ProductionProjection:
        """Return a stable projection including readiness diagnostics when blocked."""
        cap = self.caps.get(asset_id)
        asset = self.caps.assets.get(asset_id)
        readiness = self.readiness.evaluate(asset_id)
        production_references = tuple(
            sorted(
                (
                    self.library.production_reference(entry.reference_record_id)
                    for entry in self.library.list_for_cap(asset_id)
                    if entry.lifecycle
                    in {
                        CanonicalReferenceLifecycle.APPROVED,
                        CanonicalReferenceLifecycle.LOCKED,
                    }
                ),
                key=lambda reference: (
                    reference.family.value,
                    reference.view.value,
                    reference.reference_id,
                ),
            )
        )
        return ProductionProjection(
            identity=CanonicalIdentity(
                asset_id=asset.asset_id,
                canonical_name=cap.title,
                category=asset.category,
                version=cap.version,
            ),
            canonical_description=cap.canonical_description,
            facts=tuple(
                item for item in cap.facts if is_production_authority(item.authority)
            ),
            visual_identity=cap.visual_identity,
            functional_identity=tuple(
                item
                for item in cap.functional_identity
                if is_production_authority(item.authority)
            ),
            constraints=tuple(
                item for item in cap.constraints if is_production_authority(item.authority)
            ),
            production_guidance=cap.production_notes,
            semantic_tags=cap.semantic_tags,
            production_classifications=cap.production_classifications,
            behaviour_references=cap.behaviour_references,
            production_metadata=cap.production_metadata,
            structured_schema_version=cap.structured_schema_version,
            references=production_references,
            readiness=readiness,
            source_cap_version=cap.version,
        )

    def require_ready(self, asset_id: str) -> ProductionProjection:
        """Return the projection only when Production Readiness is authoritative READY."""
        projection = self.project(asset_id)
        if not projection.production_ready:
            raise ProductionProjectionBlockedError(projection)
        return projection

    def project_all(self) -> tuple[ProductionProjection, ...]:
        """Return projections for every CAP in stable asset-ID order."""
        return tuple(
            self.project(cap.asset_id)
            for cap in sorted(self.caps.list(), key=lambda profile: profile.asset_id)
        )

    def production_ready(self) -> tuple[ProductionProjection, ...]:
        """Return only projections whose authoritative Production gate is Ready."""
        return tuple(projection for projection in self.project_all() if projection.production_ready)

    def checksum(self, asset_id: str) -> str:
        """Return the deterministic projection fingerprint for invalidation/caching."""
        return self.project(asset_id).checksum()
