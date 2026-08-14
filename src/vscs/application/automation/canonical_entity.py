"""Canonical Entity & Asset Resolution Automation for Phase 19.5.5."""

from __future__ import annotations

from hashlib import sha256

from vscs.application.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionService,
    ResolvedAssetBinding,
    ResolvedCAPBinding,
)
from vscs.application.story_analysis.ai_analysis import (
    EntityResolutionService,
    StoryEntityCatalog,
)
from vscs.domain.assets import AssetCategory
from vscs.domain.story_analysis import (
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
)

from .contracts import (
    AutomationProposal,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from .service import AutomationProposalService


class CanonicalEntityAssetResolutionAutomationService:
    """Resolve Story entities against current XPD/CAP truth without creating canon."""

    def __init__(
        self,
        resolver: AssetResolutionService,
        proposals: AutomationProposalService,
        catalog: StoryEntityCatalog | None = None,
    ) -> None:
        self._resolver = resolver
        self._proposals = proposals
        self._catalog = catalog

    def generate(
        self,
        *,
        story_id: str,
        source_revision: str,
        entity_resolution: EntityResolutionResult,
    ) -> tuple[AutomationProposal, ...]:
        normalized_story = story_id.strip().upper()
        revision = source_revision.strip()
        if not normalized_story or not revision:
            raise ValueError("Story ID and source revision are required")
        if entity_resolution.story_id.strip().upper() != normalized_story:
            raise ValueError("Entity resolution belongs to another Story")
        if entity_resolution.source_revision and entity_resolution.source_revision != revision:
            raise ValueError("Entity resolution is stale for this Story revision")

        generated = tuple(
            self._proposals.save(
                self._proposal(
                    story_id=normalized_story,
                    revision=revision,
                    candidate=self._rematch_current_xpd(candidate),
                )
            )
            for candidate in entity_resolution.candidates
        )
        if not generated:
            raise ValueError("Story Analysis contains no production entities to resolve")
        return generated

    def _rematch_current_xpd(self, candidate: EntityCandidate) -> EntityCandidate:
        """Refresh only deterministic XPD identity matching; never rerun semantic AI."""
        if self._catalog is None:
            return candidate
        match_kind, asset = EntityResolutionService._match(  # noqa: SLF001
            candidate.name,
            candidate.aliases,
            candidate.category,
            self._catalog.assets(),
        )
        return candidate.model_copy(
            update={
                "match_kind": match_kind,
                "matched_asset_id": asset.asset_id if asset is not None else None,
                "matched_asset_name": asset.name if asset is not None else None,
            }
        )

    def _proposal(
        self,
        *,
        story_id: str,
        revision: str,
        candidate: EntityCandidate,
    ) -> AutomationProposal:
        expected_category = self._asset_category(candidate.category)
        dependency_fingerprint = ""

        if (
            candidate.match_kind is ResolutionMatchKind.EXISTING
            and candidate.matched_asset_id
        ):
            result = self._resolver.resolve(
                AssetResolutionRequest(
                    candidate.matched_asset_id,
                    expected_category=expected_category,
                    require_approved_asset=True,
                    require_cap=True,
                    require_approved_cap=True,
                    require_approved_references=True,
                )
            )
            canonical_status = result.status.value
            if result.fingerprint is not None:
                dependency_fingerprint = result.fingerprint.checksum
            resolution_payload: dict[str, object] = {
                "resolution_kind": "existing_canonical_asset",
                "matched_asset_id": candidate.matched_asset_id,
                "matched_asset_name": candidate.matched_asset_name or "",
                "canonical_status": canonical_status,
                "asset": self._asset_payload(result.asset),
                "cap": self._cap_payload(result.cap),
                "references": [
                    {
                        "reference_id": reference.reference_id,
                        "file_path": reference.file_path,
                        "reference_type": reference.reference_type,
                        "role": reference.role,
                        "checksum": reference.checksum,
                    }
                    for reference in result.references
                ],
                "diagnostics": [
                    {
                        "code": diagnostic.code,
                        "severity": diagnostic.severity.value,
                        "message": diagnostic.message,
                        "subject": diagnostic.subject,
                    }
                    for diagnostic in result.diagnostics
                ],
            }
        else:
            canonical_status = (
                "new_asset_required"
                if candidate.match_kind is ResolutionMatchKind.NEW
                else "human_resolution_required"
            )
            resolution_payload = {
                "resolution_kind": candidate.match_kind.value,
                "matched_asset_id": candidate.matched_asset_id or "",
                "matched_asset_name": candidate.matched_asset_name or "",
                "canonical_status": canonical_status,
                "proposed_asset_id": self._proposed_asset_id(candidate),
                "human_resolution_required": True,
            }

        payload = {
            "candidate_id": candidate.candidate_id,
            "name": candidate.name,
            "entity_category": candidate.category.value,
            "expected_asset_category": expected_category.value,
            "description": candidate.description,
            "aliases": list(candidate.aliases),
            "attributes": dict(candidate.attributes),
            "confidence": candidate.confidence,
            "match_kind": candidate.match_kind.value,
            "evidence": [span.model_dump(mode="json") for span in candidate.evidence],
            **resolution_payload,
        }
        target_id = candidate.matched_asset_id or self._proposed_asset_id(candidate)
        return AutomationProposal(
            proposal_id=self._proposal_id(story_id, revision, candidate.candidate_id),
            proposal_type=AutomationProposalType.ASSET,
            target_id=target_id,
            payload=payload,
            provenance=AutomationProvenance(
                source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
                source_story_id=story_id,
                source_revision=revision,
                source_scope=(
                    "current Story entity-resolution candidate plus authoritative XPD/CAP data"
                ),
                provider="vscs",
                model="deterministic-canonical-resolution",
                confidence=candidate.confidence,
                inference_note=(
                    "Canonical identity is resolved deterministically against current XPD/CAP "
                    "truth. Unmatched or ambiguous entities remain proposals requiring human review."
                ),
                resolution_method=(
                    "current XPD entity rematch plus authoritative Asset/CAP/reference resolution"
                ),
            ),
            metadata={
                "phase": "19.5.5",
                "candidate_id": candidate.candidate_id,
                "canonical_status": canonical_status,
                "asset_dependency_fingerprint": dependency_fingerprint,
            },
        )

    @staticmethod
    def _asset_category(category: EntityResolutionCategory) -> AssetCategory:
        mapping = {
            EntityResolutionCategory.CHARACTER: AssetCategory.CHARACTER,
            EntityResolutionCategory.SHIP: AssetCategory.SHIP,
            EntityResolutionCategory.PLANET: AssetCategory.PLANET,
            EntityResolutionCategory.LOCATION: AssetCategory.LOCATION,
            EntityResolutionCategory.VEHICLE: AssetCategory.VEHICLE,
            EntityResolutionCategory.PROP: AssetCategory.PROP,
            EntityResolutionCategory.TECHNOLOGY: AssetCategory.TECHNOLOGY,
            EntityResolutionCategory.ENVIRONMENT: AssetCategory.ENVIRONMENT,
        }
        return mapping.get(category, AssetCategory.OTHER)

    @staticmethod
    def _asset_payload(asset: ResolvedAssetBinding | None) -> dict[str, object] | None:
        if asset is None:
            return None
        return {
            "asset_id": asset.asset_id,
            "name": asset.name,
            "category": asset.category.value,
            "description": asset.description,
            "status": asset.status.value,
            "tags": list(asset.tags),
            "checksum": asset.checksum,
        }

    @staticmethod
    def _cap_payload(cap: ResolvedCAPBinding | None) -> dict[str, object] | None:
        if cap is None:
            return None
        return {
            "asset_id": cap.asset_id,
            "title": cap.title,
            "version": cap.version,
            "status": cap.status.value,
            "canonical_description": cap.canonical_description,
            "visual_identity": cap.visual_identity,
            "production_notes": cap.production_notes,
            "checksum": cap.checksum,
        }

    @staticmethod
    def _proposed_asset_id(candidate: EntityCandidate) -> str:
        category = CanonicalEntityAssetResolutionAutomationService._asset_category(
            candidate.category
        )
        normalized = "".join(
            character
            for character in candidate.name.upper()
            if character.isalnum() or character == " "
        )
        slug = "-".join(normalized.split())[:40]
        digest = sha256(candidate.candidate_id.encode("utf-8")).hexdigest()[:8].upper()
        return f"AUTO-{category.value.upper()}-{slug or 'ENTITY'}-{digest}"

    @staticmethod
    def _proposal_id(story_id: str, revision: str, candidate_id: str) -> str:
        digest = sha256(
            f"{story_id}|{revision}|asset|{candidate_id}".encode("utf-8")
        ).hexdigest()
        return f"AUT-ASSET-{digest[:12].upper()}"
