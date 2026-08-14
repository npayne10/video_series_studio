from __future__ import annotations

from typing import cast

from vscs.application.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionService,
    AssetResolutionStatus,
    ResolvedAssetBinding,
    ResolvedCAPBinding,
    ResolvedReferenceBinding,
)
from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    CanonicalEntityAssetResolutionAutomationService,
)
from vscs.application.story_analysis.ai_analysis import (
    ExistingAssetReference,
    StoryEntityCatalog,
)
from vscs.domain.assets import AssetCategory, AssetStatus
from vscs.domain.caps import CAPStatus
from vscs.domain.story_analysis import (
    EntityCandidate,
    EntityResolutionCategory,
    EntityResolutionResult,
    ResolutionMatchKind,
)


class _ProposalStore:
    def __init__(self) -> None:
        self.proposals: list[AutomationProposal] = []

    def save(self, proposal: AutomationProposal) -> AutomationProposal:
        self.proposals.append(proposal)
        return proposal

    def list_proposals(self) -> tuple[AutomationProposal, ...]:
        return tuple(self.proposals)


class _Catalog:
    def assets(self) -> tuple[ExistingAssetReference, ...]:
        return (
            ExistingAssetReference(
                asset_id="CHR-JAMES",
                name="Commander James Spence",
                category=AssetCategory.CHARACTER,
            ),
        )


class _Resolver:
    def resolve(self, request: AssetResolutionRequest) -> AssetResolutionResult:
        return AssetResolutionResult(
            request=request,
            status=AssetResolutionStatus.RESOLVED,
            asset=ResolvedAssetBinding(
                asset_id="CHR-JAMES",
                name="Commander James Spence",
                category=AssetCategory.CHARACTER,
                description="Commander",
                status=AssetStatus.APPROVED,
                tags=(),
                checksum="asset",
            ),
            cap=ResolvedCAPBinding(
                asset_id="CHR-JAMES",
                title="James",
                version="2.0",
                status=CAPStatus.APPROVED,
                canonical_description="Canonical James",
                visual_identity="James identity",
                production_notes="Maintain continuity",
                checksum="cap",
            ),
            references=(
                ResolvedReferenceBinding(
                    reference_id="REF-JAMES",
                    file_path="james.png",
                    reference_type="image",
                    role="primary",
                    checksum="reference",
                ),
            ),
        )


def test_phase_19_5_5_rematches_cached_new_entity_against_current_xpd() -> None:
    store = _ProposalStore()
    service = CanonicalEntityAssetResolutionAutomationService(
        cast(AssetResolutionService, _Resolver()),
        cast(AutomationProposalService, store),
        cast(StoryEntityCatalog, _Catalog()),
    )
    cached = EntityResolutionResult(
        story_id="STORY-001",
        source_revision="rev-1",
        candidates=(
            EntityCandidate(
                candidate_id="candidate:character:james",
                name="Commander James Spence",
                category=EntityResolutionCategory.CHARACTER,
                match_kind=ResolutionMatchKind.NEW,
            ),
        ),
    )

    proposal = service.generate(
        story_id="STORY-001",
        source_revision="rev-1",
        entity_resolution=cached,
    )[0]

    assert proposal.target_id == "CHR-JAMES"
    assert proposal.payload["match_kind"] == "existing"
    assert proposal.payload["resolution_kind"] == "existing_canonical_asset"
    assert proposal.payload["canonical_status"] == "resolved"
