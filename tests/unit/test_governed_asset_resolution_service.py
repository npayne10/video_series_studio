"""Tests for Phase 19.3.4 governed Shot asset resolution."""

from __future__ import annotations

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
