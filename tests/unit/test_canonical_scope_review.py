from pathlib import Path
from typing import cast

import pytest

from vscs.application.assets import AssetService
from vscs.application.automation import (
    AutomationProposal,
    AutomationProposalService,
    AutomationProposalType,
    AutomationProvenance,
    AutomationSourceKind,
)
from vscs.application.automation.canonical_scope_review import (
    CanonicalScope,
    CanonicalScopeReviewService,
)
from vscs.application.projects import ProjectService
from vscs.infrastructure.configuration import ConfigurationService


def _store(tmp_path: Path) -> AutomationProposalService:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration)
    projects.create(tmp_path / "project", name="Phase 19.5.12 Scope Test")
    return AutomationProposalService(projects)


def _proposal(
    proposal_id: str,
    name: str,
    category: str,
    *,
    resolution_kind: str = "new",
    matched_asset_id: str = "",
    canonical_scope: str = "",
) -> AutomationProposal:
    payload: dict[str, object] = {
        "name": name,
        "expected_asset_category": category,
        "resolution_kind": resolution_kind,
        "matched_asset_id": matched_asset_id,
    }
    if canonical_scope:
        payload["canonical_scope"] = canonical_scope
    return AutomationProposal(
        proposal_id=proposal_id,
        proposal_type=AutomationProposalType.ASSET,
        target_id=proposal_id,
        payload=payload,
        provenance=AutomationProvenance(
            source_kind=AutomationSourceKind.DETERMINISTIC_RESOLUTION,
            source_story_id="STORY-001",
            source_revision="rev-1",
            source_scope=name,
        ),
    )


def _recommend(proposal: AutomationProposal) -> CanonicalScope:
    service = CanonicalScopeReviewService(
        cast(AssetService, object()), cast(AutomationProposalService, object())
    )
    return service.recommend(proposal).scope


def test_generic_set_dressing_defaults_to_prompt_element() -> None:
    assert _recommend(_proposal("A1", "Storage cabinets", "prop")) is CanonicalScope.PROMPT_ELEMENT
    assert _recommend(_proposal("A2", "Equipment racks", "prop")) is CanonicalScope.PROMPT_ELEMENT
    assert _recommend(_proposal("A3", "Equipment case", "prop")) is CanonicalScope.PROMPT_ELEMENT


def test_stateful_prop_defaults_to_scene_continuity() -> None:
    assert (
        _recommend(_proposal("A1", "Overturned chair", "prop")) is CanonicalScope.SCENE_CONTINUITY
    )


def test_generic_location_does_not_expand_global_xpd() -> None:
    assert (
        _recommend(_proposal("A1", "Operations room", "location"))
        is CanonicalScope.SCENE_CONTINUITY
    )


def test_specific_named_location_remains_canonical_candidate() -> None:
    assert (
        _recommend(_proposal("A1", "Listening Post 17", "location"))
        is CanonicalScope.STORY_UNIQUE_CANONICAL
    )


def test_anonymous_character_presence_defaults_to_scene_continuity() -> None:
    assert (
        _recommend(_proposal("A1", "Unknown fourth figure", "character"))
        is CanonicalScope.SCENE_CONTINUITY
    )


def test_resolved_canonical_identity_is_protected_from_scope_downgrade(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(
        _proposal(
            "A1",
            "Sandra Crawford",
            "character",
            resolution_kind="existing_canonical_asset",
            matched_asset_id="CAP-CHR-003",
        )
    )
    service = CanonicalScopeReviewService(cast(AssetService, object()), store)

    with pytest.raises(ValueError, match="already has a canonical XPD identity"):
        service.set_scope(
            story_id="STORY-001",
            source_revision="rev-1",
            entity_name="Sandra Crawford",
            scope=CanonicalScope.PROMPT_ELEMENT,
        )


def test_bulk_safe_review_accepts_only_new_noncanonical_scopes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(_proposal("A1", "Storage cabinets", "prop"))
    store.save(_proposal("A2", "Operations room", "location"))
    store.save(_proposal("A3", "Listening Post 17", "location"))
    store.save(
        _proposal(
            "A4",
            "Wall display",
            "technology",
            resolution_kind="possible_duplicate",
        )
    )
    service = CanonicalScopeReviewService(cast(AssetService, object()), store)

    preview = service.preview_safe_recommendations(
        story_id="STORY-001", source_revision="rev-1"
    )
    assert preview.prompt_elements == 1
    assert preview.scene_continuity == 1
    assert preview.eligible == 2
    assert preview.skipped == 2

    result = service.accept_safe_recommendations(
        story_id="STORY-001", source_revision="rev-1", reviewed_by="Neill"
    )
    assert result.prompt_elements == 1
    assert result.scene_continuity == 1

    cabinets = service.entity_proposal("STORY-001", "rev-1", "Storage cabinets")
    operations = service.entity_proposal("STORY-001", "rev-1", "Operations room")
    listening_post = service.entity_proposal("STORY-001", "rev-1", "Listening Post 17")
    wall_display = service.entity_proposal("STORY-001", "rev-1", "Wall display")
    assert cabinets.payload["canonical_scope"] == CanonicalScope.PROMPT_ELEMENT.value
    assert operations.payload["canonical_scope"] == CanonicalScope.SCENE_CONTINUITY.value
    assert cabinets.payload["canonical_scope_resolution_source"] == "human_bulk_safe_review"
    assert operations.payload["canonical_scope_reviewed_by"] == "Neill"
    assert "canonical_scope" not in listening_post.payload
    assert "canonical_scope" not in wall_display.payload


def test_bulk_safe_review_never_overrides_prior_human_scope(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.save(
        _proposal(
            "A1",
            "Storage cabinets",
            "prop",
            canonical_scope=CanonicalScope.DEFERRED.value,
        )
    )
    service = CanonicalScopeReviewService(cast(AssetService, object()), store)

    preview = service.preview_safe_recommendations(
        story_id="STORY-001", source_revision="rev-1"
    )
    assert preview.eligible == 0
    result = service.accept_safe_recommendations(
        story_id="STORY-001", source_revision="rev-1"
    )
    assert result.eligible == 0
    proposal = service.entity_proposal("STORY-001", "rev-1", "Storage cabinets")
    assert proposal.payload["canonical_scope"] == CanonicalScope.DEFERRED.value
