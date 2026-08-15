from pathlib import Path

from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ShotAssetBindingService,
)
from vscs.application.projects import ProjectService


def _store(tmp_path: Path) -> AutomationProposalService:
    projects = ProjectService()
    projects._project_directory = tmp_path
    return AutomationProposalService(projects)


def _proposal(
    proposal_id: str, kind: AutomationProposalType, target: str, payload: dict[str, object]
) -> AutomationProposal:
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=kind,
        target_id=target,
        payload=payload,
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope=target,
        ),
    )


def test_shot_binding_reuses_resolved_canonical_asset(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(
        _proposal(
            "ASSET-1",
            AutomationProposalType.ASSET,
            "CAP-CHR-001",
            {
                "name": "Commander James Spence",
                "candidate_id": "C1",
                "aliases": ["James"],
                "resolution_kind": "existing_canonical_asset",
                "matched_asset_id": "CAP-CHR-001",
                "matched_asset_name": "Commander James Spence",
            },
        )
    )
    store.save(
        _proposal(
            "SHOT-1",
            AutomationProposalType.SHOT,
            "EP-001-SCN-001-SH-001",
            {"required_action": "James steps toward the bridge display."},
        )
    )
    report = ShotAssetBindingService(store).bind(story_id="STORY-001", source_revision="rev-1")
    assert report.binding_count == 1
    assert report.bindings[0].asset_id == "CAP-CHR-001"


def test_shot_binding_never_binds_unresolved_entity(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(
        _proposal(
            "ASSET-1",
            AutomationProposalType.ASSET,
            "AUTO-PROP-X",
            {
                "name": "Unknown Device",
                "candidate_id": "C1",
                "aliases": [],
                "resolution_kind": "new",
                "matched_asset_id": "",
            },
        )
    )
    store.save(
        _proposal(
            "SHOT-1",
            AutomationProposalType.SHOT,
            "SHOT-001",
            {"required_action": "The Unknown Device activates."},
        )
    )
    report = ShotAssetBindingService(store).bind(story_id="STORY-001", source_revision="rev-1")
    assert report.binding_count == 0
    assert report.unresolved_entity_count == 1
