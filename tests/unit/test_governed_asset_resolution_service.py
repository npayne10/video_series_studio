"""Tests for Phase 19.3.4 governed Shot asset resolution."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from vscs.application.asset_resolution import register_asset_resolution
from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.projects import ProjectService
from vscs.application.story import (
    AssetBindingStatus,
    EpisodePlanningService,
    GovernedAssetResolutionError,
    GovernedAssetResolutionService,
    GovernedShotPlanningService,
    ScenePlanningService,
    ShotAssetInferenceSource,
    ShotAssetRequirementProposal,
    StoryLifecycleService,
    StoryService,
    register_governed_asset_resolution,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate, AssetStatus, AssetUpdate
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CAPCreate,
    CAPStatus,
)


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _planning(tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Demo", name="Demo")
    lifecycle = StoryLifecycleService(projects)
    story = lifecycle.create_story(title="Xorix")
    episodes = EpisodePlanningService(projects, lifecycle)
    episode = episodes.create(
        story_id=story.story_id,
        sequence_number=1,
        title="Arrival",
        story_scope="Arrival in orbit.",
        production_objective="Establish Xorix.",
        target_runtime_seconds=600,
    )
    episode = episodes.mark_ready(episode.episode_id)
    scenes = ScenePlanningService(projects, episodes, StoryService(projects))
    scene = scenes.create(
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Orbital Arrival",
        story_scope="Mauritania settles into orbit.",
        production_objective="Establish planetary scale.",
        target_runtime_seconds=60,
        setting_requirement="Xorix orbit",
        required_events=("Xorix fills the forward view",),
    )
    scene = scenes.mark_ready(scene.scene_id)
    from vscs.application.shots import ShotPlanningService

    shots = GovernedShotPlanningService(
        projects,
        scenes,
        context.services.require(ShotPlanningService),
    )
    shot = shots.create(
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Reveal Xorix",
        narrative_purpose="Reveal the scale of Xorix.",
        production_objective="Orient the audience.",
        target_runtime_seconds=10,
        required_action="Mauritania crosses frame above Xorix.",
    )
    shot = shots.mark_ready(shot.shot_id)
    context.services.register(GovernedShotPlanningService, shots)
    register_asset_resolution(context.services)
    governed_assets = register_governed_asset_resolution(context.services)
    return context, shots, governed_assets, shot


def _approved_ship(context, tmp_path: Path, asset_id: str = "CAP-SHP-IRON-HORIZON") -> str:
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate(
            asset_id=asset_id,
            name="Iron Horizon",
            category=AssetCategory.SHIP,
            description="Guild survey spacecraft.",
            status=AssetStatus.APPROVED,
        )
    )
    caps = context.services.require(CAPService)
    cap = caps.create(
        CAPCreate(
            asset_id=asset_id,
            title="Iron Horizon",
            version="2.0",
            status=CAPStatus.APPROVED,
            canonical_description="A 145 metre Guild survey spacecraft.",
            visual_identity="Four rear fusion engines.",
            production_notes="Controlled blue-white engine trails.",
        )
    )
    reference_path = tmp_path / "Demo" / "references" / "iron_horizon.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(b"reference")
    references = context.services.require(CanonicalReferenceService)
    created = references.create(
        asset_id,
        CanonicalReferenceCreate(
            cap_id=cap.id,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.PRIMARY,
            title="Iron Horizon primary",
            file_path=reference_path,
        ),
    )
    candidate = references.mark_candidate(created.id)
    references.approve(candidate.id, "Neill")
    return asset_id


def _approved_named_asset(
    context,
    tmp_path: Path,
    *,
    asset_id: str,
    name: str,
    category: AssetCategory,
) -> str:
    assets = context.services.require(AssetService)
    assets.create(
        AssetCreate(
            asset_id=asset_id,
            name=name,
            category=category,
            description=f"Canonical {category.value} asset for {name}.",
            status=AssetStatus.APPROVED,
        )
    )
    caps = context.services.require(CAPService)
    cap = caps.create(
        CAPCreate(
            asset_id=asset_id,
            title=name,
            version="1.0",
            status=CAPStatus.APPROVED,
            canonical_description=f"Canonical production identity for {name}.",
            visual_identity=f"Approved visual identity for {name}.",
            production_notes="Preserve approved canonical identity.",
        )
    )
    reference_path = tmp_path / "Demo" / "references" / f"{asset_id}.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(b"reference")
    references = context.services.require(CanonicalReferenceService)
    created = references.create(
        asset_id,
        CanonicalReferenceCreate(
            cap_id=cap.id,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.PRIMARY,
            title=f"{name} primary",
            file_path=reference_path,
        ),
    )
    candidate = references.mark_candidate(created.id)
    references.approve(candidate.id, "Neill")
    return asset_id


def _binding(
    service: GovernedAssetResolutionService,
    shot_id: str,
    *,
    asset_id: str = "",
):
    return service.create(
        shot_id=shot_id,
        sequence_number=1,
        role="Hero spacecraft",
        requirement="The Iron Horizon must be visible and canonically identifiable.",
        expected_category=AssetCategory.SHIP,
        asset_id=asset_id,
    )


def test_draft_requirement_can_be_saved_unbound(tmp_path: Path) -> None:
    context, _shots, service, shot = _planning(tmp_path)
    binding = _binding(service, shot.shot_id)

    assert binding.binding_id == f"{shot.shot_id}-AST-001"
    assert binding.status is AssetBindingStatus.DRAFT
    assert binding.asset_id == ""
    assert service.list_bindings(shot_id=shot.shot_id) == (binding,)
    context.shutdown()


def test_asset_resolution_requires_current_ready_shot(tmp_path: Path) -> None:
    context, shots, service, shot = _planning(tmp_path)
    shots.return_to_draft(shot.shot_id)

    with pytest.raises(GovernedAssetResolutionError, match="Ready governed Shot Plan"):
        _binding(service, shot.shot_id)
    context.shutdown()


def test_camera_and_lighting_categories_are_owned_by_later_planners(tmp_path: Path) -> None:
    context, _shots, service, shot = _planning(tmp_path)

    with pytest.raises(GovernedAssetResolutionError, match="Camera Planner"):
        service.create(
            shot_id=shot.shot_id,
            sequence_number=1,
            role="Camera profile",
            requirement="A restrained orbital reveal.",
            expected_category=AssetCategory.CAMERA,
        )
    context.shutdown()


def test_ready_binding_requires_approved_asset_cap_and_reference(tmp_path: Path) -> None:
    context, _shots, service, shot = _planning(tmp_path)
    asset_id = _approved_ship(context, tmp_path)
    binding = _binding(service, shot.shot_id, asset_id=asset_id)

    ready = service.mark_ready(binding.binding_id)

    assert ready.status is AssetBindingStatus.READY
    assert service.is_production_ready(ready)
    assert service.shot_ready(shot.shot_id)
    context.shutdown()


def test_ready_binding_must_return_to_draft_before_reapproval(tmp_path: Path) -> None:
    context, _shots, service, shot = _planning(tmp_path)
    asset_id = _approved_ship(context, tmp_path)
    ready = service.mark_ready(_binding(service, shot.shot_id, asset_id=asset_id).binding_id)

    context.services.require(AssetService).update(
        asset_id,
        AssetUpdate(description="Changed after approval."),
    )

    with pytest.raises(GovernedAssetResolutionError, match="return to Draft"):
        service.mark_ready(ready.binding_id)
    context.shutdown()


def test_asset_change_marks_ready_binding_stale(tmp_path: Path) -> None:
    context, _shots, service, shot = _planning(tmp_path)
    asset_id = _approved_ship(context, tmp_path)
    ready = service.mark_ready(_binding(service, shot.shot_id, asset_id=asset_id).binding_id)
    assert service.is_asset_current(ready)

    context.services.require(AssetService).update(
        asset_id,
        AssetUpdate(description="Updated canonical registry description."),
    )

    stale = service.binding(ready.binding_id)
    assert stale is not None
    assert not service.is_asset_current(stale)
    assert not service.is_production_ready(stale)
    context.shutdown()


def test_shot_change_marks_asset_binding_stale(tmp_path: Path) -> None:
    context, shots, service, shot = _planning(tmp_path)
    asset_id = _approved_ship(context, tmp_path)
    ready = service.mark_ready(_binding(service, shot.shot_id, asset_id=asset_id).binding_id)
    assert service.is_upstream_current(ready)

    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title=draft.title,
        narrative_purpose=draft.narrative_purpose,
        production_objective="Orient the audience and establish ship scale.",
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action=draft.required_action,
        dialogue_requirement=draft.dialogue_requirement,
        continuity_in=draft.continuity_in,
        continuity_out=draft.continuity_out,
        shot_constraints=draft.shot_constraints,
    )
    shots.mark_ready(updated.shot_id)

    stale = service.binding(ready.binding_id)
    assert stale is not None
    assert not service.is_upstream_current(stale)
    assert not service.is_production_ready(stale)
    context.shutdown()


def test_inference_extracts_explicit_shot_asset_and_matches_current_canonical_authority(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    asset_id = _approved_ship(context, tmp_path)
    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title="Iron Horizon Establish",
        narrative_purpose="Establish the Iron Horizon in Xorix orbit.",
        production_objective=draft.production_objective,
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action="The Iron Horizon crosses frame above Xorix.",
        dialogue_requirement=draft.dialogue_requirement,
        continuity_in=draft.continuity_in,
        continuity_out=draft.continuity_out,
        shot_constraints=draft.shot_constraints,
    )
    shots.mark_ready(updated.shot_id)

    proposals = service.infer_requirements(updated.shot_id, include_ai=False)

    matched = next(proposal for proposal in proposals if proposal.matched_asset_id == asset_id)
    assert matched.expected_category is AssetCategory.SHIP
    assert matched.source is ShotAssetInferenceSource.CANONICAL_MATCH
    assert matched.confidence == 1.0
    assert matched.canonical_status == "resolved"
    assert "Explicit canonical asset name" in matched.rationale
    context.shutdown()


def test_inferred_requirements_materialize_only_as_draft_bindings(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    asset_id = _approved_ship(context, tmp_path)
    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title="Iron Horizon Establish",
        narrative_purpose="Establish the Iron Horizon.",
        production_objective=draft.production_objective,
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action="The Iron Horizon crosses frame.",
        dialogue_requirement="",
        continuity_in="",
        continuity_out="",
        shot_constraints=(),
    )
    updated = shots.mark_ready(updated.shot_id)
    proposals = service.infer_requirements(updated.shot_id, include_ai=False)

    created = service.apply_inferred_requirements(updated.shot_id, proposals)

    assert created
    assert all(binding.status is AssetBindingStatus.DRAFT for binding in created)
    assert any(binding.asset_id == asset_id for binding in created)
    assert not service.shot_ready(updated.shot_id)
    context.shutdown()


def test_optional_ai_inference_runs_only_when_deterministic_requirements_are_insufficient(
    tmp_path: Path,
) -> None:
    context, _shots, service, shot = _planning(tmp_path)

    class _AIProvider:
        provider_name = "test-ai"
        model_name = "semantic-test"

        def __init__(self) -> None:
            self.calls = 0

        def infer_requirements(self, *, shot, scene_text, deterministic):
            self.calls += 1
            assert shot.shot_id
            assert scene_text
            assert deterministic == ()
            return (
                ShotAssetRequirementProposal(
                    proposal_id=f"{shot.shot_id}-AI-001",
                    shot_id=shot.shot_id,
                    role="Information-bearing Shot element",
                    requirement="Signal display is required to show the repeating pattern.",
                    expected_category=AssetCategory.TECHNOLOGY,
                    confidence=0.78,
                    source=ShotAssetInferenceSource.AI_SEMANTIC,
                    rationale="Semantic inference from the governed required action.",
                    canonical_status="unresolved",
                ),
            )

    provider = _AIProvider()
    service.semantic_provider = provider

    proposals = service.infer_requirements(shot.shot_id)

    assert provider.calls == 1
    assert len(proposals) == 1
    assert proposals[0].source is ShotAssetInferenceSource.AI_SEMANTIC
    assert proposals[0].matched_asset_id == ""
    created = service.apply_inferred_requirements(shot.shot_id, proposals)
    assert len(created) == 1
    assert created[0].asset_id == ""
    assert created[0].status is AssetBindingStatus.DRAFT
    context.shutdown()


def test_optional_ai_is_not_called_when_deterministic_canonical_match_is_sufficient(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    _approved_ship(context, tmp_path)
    draft = shots.return_to_draft(shot.shot_id)
    updated = replace(
        draft,
        title="Iron Horizon",
        required_action="Iron Horizon crosses frame.",
    )
    shots._replace(updated)
    shots.mark_ready(updated.shot_id)

    class _UnexpectedAI:
        provider_name = "test-ai"
        model_name = "should-not-run"

        def infer_requirements(self, **_kwargs):
            raise AssertionError("AI should not run when deterministic matching is sufficient")

    service.semantic_provider = _UnexpectedAI()

    proposals = service.infer_requirements(updated.shot_id)

    assert any(proposal.matched_asset_id == "CAP-SHP-IRON-HORIZON" for proposal in proposals)
    context.shutdown()


def test_inference_suppresses_story_placeholder_when_canonical_asset_covers_same_entity(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    _approved_named_asset(
        context,
        tmp_path,
        asset_id="CAP-PLN-002",
        name="Xorix",
        category=AssetCategory.PLANET,
    )
    context.services.require(AssetService).create(
        AssetCreate(
            asset_id="STORY-LOC-B6E569C147",
            name="Xorix system",
            category=AssetCategory.LOCATION,
            description="Story-derived placeholder location.",
            status=AssetStatus.APPROVED,
        )
    )
    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title="Xorix Reveal",
        narrative_purpose="Show Xorix beyond the bridge.",
        production_objective=draft.production_objective,
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action="Xorix remains visible on the forward display.",
        dialogue_requirement="",
        continuity_in="",
        continuity_out="",
        shot_constraints=(),
    )
    shots.mark_ready(updated.shot_id)

    proposals = service.infer_requirements(updated.shot_id, include_ai=False)

    assert any(proposal.matched_asset_id == "CAP-PLN-002" for proposal in proposals)
    assert all(
        proposal.matched_asset_id != "STORY-LOC-B6E569C147" for proposal in proposals
    )
    context.shutdown()


def test_inference_classifies_dialogue_speaker_and_supporting_character(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    _approved_named_asset(
        context,
        tmp_path,
        asset_id="CAP-CHR-002",
        name="Captain Cheryl Draker",
        category=AssetCategory.CHARACTER,
    )
    _approved_named_asset(
        context,
        tmp_path,
        asset_id="CAP-CHR-001",
        name="Commander James Spence",
        category=AssetCategory.CHARACTER,
    )
    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title="Put It Through — Dialogue",
        narrative_purpose="Let the bridge hear the signal.",
        production_objective="Move the anomaly into direct investigation.",
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action=(
            "Captain Cheryl Draker orders the signal put through. "
            "Commander James Spence watches the display."
        ),
        dialogue_requirement="Put it through.",
        continuity_in="",
        continuity_out="",
        shot_constraints=(),
    )
    shots.mark_ready(updated.shot_id)

    proposals = service.infer_requirements(updated.shot_id, include_ai=False)
    by_asset = {proposal.matched_asset_id: proposal for proposal in proposals}

    assert by_asset["CAP-CHR-002"].role == "Dialogue Speaker"
    assert by_asset["CAP-CHR-001"].role == "Supporting Character"
    context.shutdown()


def test_inference_uses_specific_production_role_labels_for_asset_categories(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    for asset_id, name, category in (
        ("CAP-LOC-008", "Bridge", AssetCategory.LOCATION),
        ("CAP-ENV-004", "Xorix Orbit", AssetCategory.ENVIRONMENT),
        ("CAP-PLN-002", "Xorix", AssetCategory.PLANET),
        ("CAP-SHP-002", "Iron Horizon", AssetCategory.SHIP),
        ("CAP-TEC-001", "Signal Display", AssetCategory.TECHNOLOGY),
    ):
        _approved_named_asset(
            context,
            tmp_path,
            asset_id=asset_id,
            name=name,
            category=category,
        )
    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title="Signal Display in Xorix Orbit",
        narrative_purpose="Show the signal detail on the Bridge.",
        production_objective="Preserve the Iron Horizon bridge context.",
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action=(
            "On the Bridge of the Iron Horizon, show the Signal Display with Xorix visible "
            "while the ship remains in Xorix Orbit."
        ),
        dialogue_requirement="",
        continuity_in="",
        continuity_out="",
        shot_constraints=(),
    )
    shots.mark_ready(updated.shot_id)

    proposals = service.infer_requirements(updated.shot_id, include_ai=False)
    roles = {proposal.matched_asset_id: proposal.role for proposal in proposals}

    assert roles["CAP-LOC-008"] == "Location"
    assert roles["CAP-ENV-004"] == "Environment Context"
    assert roles["CAP-PLN-002"] == "Visible Planet"
    assert roles["CAP-SHP-002"] == "Vehicle/Ship"
    assert roles["CAP-TEC-001"] == "Prop/Technology"
    context.shutdown()


def test_environment_family_keeps_distinct_location_environment_and_visible_planet(
    tmp_path: Path,
) -> None:
    context, shots, service, shot = _planning(tmp_path)
    for asset_id, name, category in (
        ("CAP-LOC-008", "Iron Horizon Bridge", AssetCategory.LOCATION),
        ("CAP-ENV-004", "Xorix Orbit", AssetCategory.ENVIRONMENT),
        ("CAP-PLN-002", "Xorix", AssetCategory.PLANET),
    ):
        _approved_named_asset(
            context,
            tmp_path,
            asset_id=asset_id,
            name=name,
            category=category,
        )
    draft = shots.return_to_draft(shot.shot_id)
    updated = shots.update(
        draft.shot_id,
        title="Bridge Over Xorix",
        narrative_purpose="Establish the Iron Horizon Bridge in Xorix Orbit.",
        production_objective=draft.production_objective,
        target_runtime_seconds=draft.target_runtime_seconds,
        required_action="Show Xorix from the Iron Horizon Bridge while in Xorix Orbit.",
        dialogue_requirement="",
        continuity_in="",
        continuity_out="",
        shot_constraints=(),
    )
    shots.mark_ready(updated.shot_id)

    proposals = service.infer_requirements(updated.shot_id, include_ai=False)
    ids = {proposal.matched_asset_id for proposal in proposals}

    assert {"CAP-LOC-008", "CAP-ENV-004", "CAP-PLN-002"}.issubset(ids)
    context.shutdown()
