from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ProposalReviewGapDetectionService,
)
from vscs.application.projects import ProjectService


def _store(tmp_path: Path) -> AutomationProposalService:
    projects = ProjectService()
    projects._project_directory = tmp_path
    return AutomationProposalService(projects)


def _proposal(proposal_id: str, proposal_type: AutomationProposalType, target: str, payload: dict[str, object]) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        target_id=target,
        payload=payload,
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope=target,
            resolution_method="test",
        ),
    )


def test_review_detects_unresolved_assets_and_missing_specialists(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_proposal("AUT-SHOT-1", AutomationProposalType.SHOT, "SHOT-001", {}))
    store.save(_proposal("AUT-ASSET-1", AutomationProposalType.ASSET, "ENTITY-001", {"canonical_status": "review_required"}))
    report = ProposalReviewGapDetectionService(store).review(story_id="STORY-001", source_revision="rev-1")
    assert report.blocker_count == 6
    assert {gap.category for gap in report.gaps} == {"canonical_asset", "missing_specialist_proposal"}


def test_review_is_read_only(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_proposal("AUT-SHOT-1", AutomationProposalType.SHOT, "SHOT-001", {}))
    before = store.list_proposals()
    ProposalReviewGapDetectionService(store).review(story_id="STORY-001", source_revision="rev-1")
    assert store.list_proposals() == before
