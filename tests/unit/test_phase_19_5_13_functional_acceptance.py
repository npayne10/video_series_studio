from __future__ import annotations

from pathlib import Path

from vscs.application.automation import (
    AcceptanceState,
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalStatus,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    FunctionalAcceptanceService,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService


def _store(tmp_path: Path) -> AutomationProposalService:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration)
    projects.create(tmp_path / "project", name="Phase 19.5.13 Test")
    return AutomationProposalService(projects)


def _proposal(
    proposal_id: str,
    proposal_type: AutomationProposalType,
    target_id: str,
    payload: dict[str, object] | None = None,
    *,
    status: AutomationProposalStatus = AutomationProposalStatus.PROPOSED,
    accepted_by: str = "",
) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=proposal_type,
        target_id=target_id,
        payload=payload or {},
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope="Phase 19.5.13 acceptance test",
        ),
        status=status,
        reviewed_by=accepted_by,
        accepted_by=accepted_by,
    )


def _complete_set(store: AutomationProposalService) -> None:
    store.save(_proposal("EP-1", AutomationProposalType.EPISODE, "EP-001"))
    store.save(_proposal("SC-1", AutomationProposalType.SCENE, "EP-001-SCN-001"))
    store.save(_proposal("SH-1", AutomationProposalType.SHOT, "EP-001-SCN-001-SH-001"))
    for index, kind in enumerate(
        (
            AutomationProposalType.ACTION_PERFORMANCE,
            AutomationProposalType.ENVIRONMENT,
            AutomationProposalType.CAMERA,
            AutomationProposalType.LIGHTING,
            AutomationProposalType.CONTINUITY,
        ),
        start=1,
    ):
        store.save(_proposal(f"SPEC-{index}", kind, "EP-001-SCN-001-SH-001"))
    store.save(
        _proposal(
            "ASSET-1",
            AutomationProposalType.ASSET,
            "CAP-CHR-001",
            {
                "name": "Commander James Spence",
                "resolution_kind": "existing_canonical_asset",
                "matched_asset_id": "CAP-CHR-001",
                "canonical_scope": "project_canonical",
            },
        )
    )
    store.save(
        _proposal(
            "ASSET-2",
            AutomationProposalType.ASSET,
            "AUTO-PROP-1",
            {
                "name": "Storage cabinets",
                "resolution_kind": "new",
                "canonical_scope": "prompt_element",
            },
        )
    )


def test_complete_phase_19_revision_passes_acceptance(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _complete_set(store)

    report = FunctionalAcceptanceService(store).evaluate(
        story_id="STORY-001", source_revision="rev-1"
    )

    assert report.failed == 0
    assert report.review_required == 0
    assert report.accepted
    assert all(item.state is AcceptanceState.PASS for item in report.criteria)


def test_missing_specialist_and_unresolved_canon_require_review(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_proposal("EP-1", AutomationProposalType.EPISODE, "EP-001"))
    store.save(_proposal("SC-1", AutomationProposalType.SCENE, "EP-001-SCN-001"))
    store.save(_proposal("SH-1", AutomationProposalType.SHOT, "EP-001-SCN-001-SH-001"))
    store.save(
        _proposal(
            "ASSET-1",
            AutomationProposalType.ASSET,
            "AUTO-LOC-1",
            {
                "name": "Listening Post 17",
                "resolution_kind": "new",
                "canonical_scope": "story_unique_canonical",
            },
        )
    )

    report = FunctionalAcceptanceService(store).evaluate(
        story_id="STORY-001", source_revision="rev-1"
    )

    states = {item.key: item.state for item in report.criteria}
    assert states["specialist-coverage"] is AcceptanceState.REVIEW
    assert states["shot-specialist-coverage"] is AcceptanceState.REVIEW
    assert states["canonical-governance"] is AcceptanceState.REVIEW
    assert not report.accepted


def test_accepted_proposal_without_human_identity_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _complete_set(store)
    store.save(
        _proposal(
            "BAD-ACCEPT",
            AutomationProposalType.STYLE,
            "STYLE-1",
            status=AutomationProposalStatus.ACCEPTED,
        )
    )

    report = FunctionalAcceptanceService(store).evaluate(
        story_id="STORY-001", source_revision="rev-1"
    )

    criterion = next(item for item in report.criteria if item.key == "human-acceptance-integrity")
    assert criterion.state is AcceptanceState.FAIL
    assert report.failed == 1
    assert not report.accepted


def test_final_approval_marker_in_automation_proposal_fails(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _complete_set(store)
    store.save(
        _proposal(
            "BAD-APPROVAL",
            AutomationProposalType.STYLE,
            "STYLE-1",
            {"production_approved": True},
        )
    )

    report = FunctionalAcceptanceService(store).evaluate(
        story_id="STORY-001", source_revision="rev-1"
    )

    criterion = next(item for item in report.criteria if item.key == "approval-boundary")
    assert criterion.state is AcceptanceState.FAIL
    assert not report.accepted
