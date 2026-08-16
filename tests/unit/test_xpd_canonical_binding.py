from pathlib import Path
from typing import cast

from vscs.application.assets import AssetService
from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
    ShotAssetBindingService,
)
from vscs.application.automation.xpd_binding import CanonicalMatchDiagnosticService
from vscs.application.projects import ProjectService
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.infrastructure.configuration import ConfigurationService


def _store(tmp_path: Path) -> AutomationProposalService:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration)
    projects.create(tmp_path / "project", name="Phase 19.5.12 Test")
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


def _asset(asset_id: str, name: str, category: AssetCategory) -> Asset:
    return Asset(
        id=1,
        asset_id=asset_id,
        name=name,
        category=category,
        description="",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=(),
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


def test_prompt_and_scene_continuity_entities_are_not_global_canonical_blockers(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    for proposal_id, name, scope in (
        ("ASSET-1", "Storage cabinets", "prompt_element"),
        ("ASSET-2", "Overturned chair", "scene_continuity"),
    ):
        store.save(
            _proposal(
                proposal_id,
                AutomationProposalType.ASSET,
                proposal_id,
                {
                    "name": name,
                    "candidate_id": proposal_id,
                    "aliases": [],
                    "resolution_kind": "new",
                    "matched_asset_id": "",
                    "canonical_scope": scope,
                },
            )
        )
    report = ShotAssetBindingService(store).bind(story_id="STORY-001", source_revision="rev-1")
    assert report.binding_count == 0
    assert report.unresolved_entity_count == 0


def test_diagnostic_scores_rank_normalized_character_match_highly() -> None:
    match = CanonicalMatchDiagnosticService._score(
        "James Spence",
        _asset("CAP-CHR-001", "Commander James Spence", AssetCategory.CHARACTER),
    )
    assert match is not None
    assert match.asset_id == "CAP-CHR-001"
    assert match.score >= 0.98
    assert "rank/title" in match.reason


def test_diagnostic_does_not_offer_weak_unrelated_match() -> None:
    match = CanonicalMatchDiagnosticService._score(
        "Listening Post 17",
        _asset("CAP-LOC-001", "Mauritania Bridge", AssetCategory.LOCATION),
    )
    assert match is None


def test_diagnostic_does_not_repeat_human_rejected_candidate() -> None:
    service = CanonicalMatchDiagnosticService(
        cast(AssetService, object()), cast(AutomationProposalService, object())
    )
    proposal = _proposal(
        "ASSET-1",
        AutomationProposalType.ASSET,
        "AUTO-TEC-1",
        {
            "name": "Wall display",
            "expected_asset_category": "technology",
            "resolution_kind": "new",
            "matched_asset_id": "",
            "rejected_canonical_asset_ids": ["CAP-TEC-002"],
        },
    )
    diagnostic = service._diagnostic(
        proposal,
        (_asset("CAP-TEC-002", "Tactical Display", AssetCategory.TECHNOLOGY),),
    )
    assert diagnostic.status == "no_match"
    assert diagnostic.suggestions == ()
