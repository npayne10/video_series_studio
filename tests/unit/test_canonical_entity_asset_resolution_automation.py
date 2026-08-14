from __future__ import annotations

from typing import cast

import pytest

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
    AutomationProposalStatus,
    AutomationProposalType,
    CanonicalEntityAssetResolutionAutomationService,
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

    def list_proposals(self) -> tuple[AutomationProposal, ...]:
        return tuple(self.proposals)

    def save(self, proposal: AutomationProposal) -> AutomationProposal:
        self.proposals = [
            item for item in self.proposals if item.proposal_id != proposal.proposal_id
        ]
        self.proposals.append(proposal)
        return proposal


class _Resolver:
    def __init__(self, result: AssetResolutionResult | None = None) -> None:
        self.result = result
        self.requests: list[AssetResolutionRequest] = []

    def resolve(self, request: AssetResolutionRequest) -> AssetResolutionResult:
        self.requests.append(request)
        if self.result is None:
            raise AssertionError("Resolver should not have been called")
        return self.result


def _service(
    resolver: _Resolver,
) -> tuple[CanonicalEntityAssetResolutionAutomationService, _ProposalStore]:
    store = _ProposalStore()
    return (
        CanonicalEntityAssetResolutionAutomationService(
            cast(AssetResolutionService, resolver),
            cast(AutomationProposalService, store),
        ),
        store,
    )


def _existing_result() -> AssetResolutionResult:
    request = AssetResolutionRequest(
        "CHR-JAMES",
        expected_category=AssetCategory.CHARACTER,
    )
    return AssetResolutionResult(
        request=request,
        status=AssetResolutionStatus.RESOLVED,
        asset=ResolvedAssetBinding(
            asset_id="CHR-JAMES",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            description="Commander of the mission.",
            status=AssetStatus.APPROVED,
            tags=("xorix",),
            checksum="asset-checksum",
        ),
        cap=ResolvedCAPBinding(
            asset_id="CHR-JAMES",
            title="Commander James Spence",
            version="2.0",
            status=CAPStatus.APPROVED,
            canonical_description="Canonical James description",
            visual_identity="Canonical James visual identity",
            production_notes="Maintain continuity",
            checksum="cap-checksum",
        ),
        references=(
            ResolvedReferenceBinding(
                reference_id="REF-JAMES-PRIMARY",
                file_path="references/james.png",
                reference_type="image",
                role="primary",
                checksum="reference-checksum",
            ),
        ),
    )


def test_existing_entity_resolves_to_current_canonical_asset_proposal() -> None:
    resolver = _Resolver(_existing_result())
    service, _store = _service(resolver)
    entity_resolution = EntityResolutionResult(
        story_id="STORY-001",
        source_revision="rev-1",
        candidates=(
            EntityCandidate(
                candidate_id="candidate:character:james",
                name="Commander James Spence",
                category=EntityResolutionCategory.CHARACTER,
                confidence=0.98,
                match_kind=ResolutionMatchKind.EXISTING,
                matched_asset_id="CHR-JAMES",
                matched_asset_name="Commander James Spence",
            ),
        ),
    )

    proposals = service.generate(
        story_id="STORY-001",
        source_revision="rev-1",
        entity_resolution=entity_resolution,
    )

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.proposal_type is AutomationProposalType.ASSET
    assert proposal.status is AutomationProposalStatus.PROPOSED
    assert not proposal.consumable
    assert proposal.target_id == "CHR-JAMES"
    assert proposal.payload["resolution_kind"] == "existing_canonical_asset"
    assert proposal.payload["canonical_status"] == "resolved"
    assert proposal.payload["matched_asset_id"] == "CHR-JAMES"
    assert proposal.metadata["asset_dependency_fingerprint"]
    assert len(resolver.requests) == 1
    assert resolver.requests[0].require_approved_asset
    assert resolver.requests[0].require_approved_cap
    assert resolver.requests[0].require_approved_references


def test_new_entity_remains_asset_proposal_without_creating_canon() -> None:
    resolver = _Resolver()
    service, _store = _service(resolver)
    entity_resolution = EntityResolutionResult(
        story_id="STORY-001",
        source_revision="rev-1",
        candidates=(
            EntityCandidate(
                candidate_id="candidate:prop:unknown-instrument",
                name="Unidentified instrument",
                category=EntityResolutionCategory.PROP,
                description="Compact instrument found in the abandoned station.",
                confidence=0.91,
                match_kind=ResolutionMatchKind.NEW,
            ),
        ),
    )

    proposal = service.generate(
        story_id="STORY-001",
        source_revision="rev-1",
        entity_resolution=entity_resolution,
    )[0]

    assert proposal.proposal_type is AutomationProposalType.ASSET
    assert proposal.status is AutomationProposalStatus.PROPOSED
    assert proposal.payload["resolution_kind"] == "new"
    assert proposal.payload["canonical_status"] == "new_asset_required"
    assert proposal.payload["human_resolution_required"] is True
    assert str(proposal.payload["proposed_asset_id"]).startswith("AUTO-PROP-")
    assert resolver.requests == []


def test_canonical_entity_resolution_rejects_stale_story_analysis() -> None:
    service, _store = _service(_Resolver())
    entity_resolution = EntityResolutionResult(
        story_id="STORY-001",
        source_revision="old-revision",
        candidates=(
            EntityCandidate(
                candidate_id="candidate:ship:iron-horizon",
                name="Iron Horizon",
                category=EntityResolutionCategory.SHIP,
            ),
        ),
    )

    with pytest.raises(ValueError, match="stale"):
        service.generate(
            story_id="STORY-001",
            source_revision="rev-2",
            entity_resolution=entity_resolution,
        )
