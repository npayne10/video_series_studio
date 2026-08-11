from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.story import (
    AssetBindingStatus,
    CameraAngle,
    CameraMovement,
    CameraPlan,
    CameraPlanStatus,
    ExposureIntent,
    GovernedLightingPlanningError,
    GovernedLightingPlanningService,
    LensFamily,
    LightingIntent,
    LightingPlanStatus,
    ScreenDirection,
    ShotAssetBinding,
    ShotPlan,
    ShotPlanStatus,
    ShotSize,
)
from vscs.domain.assets import AssetCategory


@dataclass
class FakeProjects:
    project_directory: Path


class FakeShots:
    def __init__(self, shot: ShotPlan) -> None:
        self.shot = shot

    def plan(self, shot_id: str) -> ShotPlan | None:
        return self.shot if shot_id.strip().upper() == self.shot.shot_id else None

    def is_production_ready(self, shot: ShotPlan) -> bool:
        return shot.status is ShotPlanStatus.READY


class FakeAssets:
    def __init__(self, shot_id: str) -> None:
        self.ready = True
        self.binding = ShotAssetBinding(
            binding_id=f"{shot_id}-AST-001",
            shot_id=shot_id,
            sequence_number=1,
            role="Primary subject",
            requirement="Required subject",
            expected_category=AssetCategory.SHIP,
            asset_id="CAP-SHP-001",
            shot_contract_hash="shot",
            asset_dependency_hash="asset-v1",
            status=AssetBindingStatus.READY,
        )

    def shot_ready(self, shot_id: str) -> bool:
        return self.ready and shot_id == self.binding.shot_id

    def list_bindings(self, *, shot_id: str | None = None):
        if shot_id is None or shot_id == self.binding.shot_id:
            return (self.binding,)
        return ()

    def is_production_ready(self, binding: ShotAssetBinding) -> bool:
        return self.ready and binding.asset_dependency_hash == self.binding.asset_dependency_hash


class FakeCamera:
    def __init__(self, plan: CameraPlan) -> None:
        self.camera_plan = plan

    def plan(self, shot_id: str) -> CameraPlan | None:
        return self.camera_plan if shot_id.strip().upper() == self.camera_plan.shot_id else None

    def is_production_ready(self, plan: CameraPlan) -> bool:
        return plan.status is CameraPlanStatus.READY and plan == self.camera_plan


class FakeResolver:
    def resolve(self, _request):
        raise AssertionError("Lighting profile resolution was not expected in this test")


class FakeBrowser:
    def browse(self, _filter):
        return SimpleNamespace(items=())


def _shot(*, dialogue: str = "") -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Orbital arrival",
        narrative_purpose="Establish the planet and spacecraft scale",
        production_objective="Ground the arrival in believable orbital geography",
        target_runtime_seconds=12,
        required_action="Mauritania approaches Xorix in stable orbital flight",
        dialogue_requirement=dialogue,
        continuity_in="Ship emerges from transit",
        continuity_out="Orbital insertion established",
        scene_contract_hash="scene-v1",
        status=ShotPlanStatus.READY,
    )


def _camera(shot_id: str) -> CameraPlan:
    return CameraPlan(
        camera_plan_id=f"{shot_id}-CAM",
        shot_id=shot_id,
        shot_size=ShotSize.WIDE,
        angle=CameraAngle.EYE_LEVEL,
        movement=CameraMovement.TRACK,
        lens_family=LensFamily.WIDE,
        focal_length_mm=28,
        camera_height_m=1.6,
        screen_direction=ScreenDirection.LEFT_TO_RIGHT,
        composition="Preserve readable orbital geography",
        focus_strategy="Maintain physically plausible depth",
        movement_notes="Track at stable speed",
        continuity_notes="Preserve screen direction",
        shot_contract_hash="shot-hash",
        asset_context_hash="asset-hash",
        status=CameraPlanStatus.READY,
    )


def _service(tmp_path: Path, shot: ShotPlan | None = None):
    selected = shot or _shot()
    shots = FakeShots(selected)
    assets = FakeAssets(selected.shot_id)
    camera = FakeCamera(_camera(selected.shot_id))
    service = GovernedLightingPlanningService(
        FakeProjects(tmp_path),  # type: ignore[arg-type]
        shots,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        camera,  # type: ignore[arg-type]
        FakeResolver(),  # type: ignore[arg-type]
        FakeBrowser(),  # type: ignore[arg-type]
    )
    return service, shots, assets, camera


def _refresh_draft(service: GovernedLightingPlanningService, shot_id: str):
    plan = service.plan(shot_id)
    assert plan is not None
    return service.update(
        shot_id,
        lighting_intent=plan.lighting_intent,
        key_direction=plan.key_direction,
        key_quality=plan.key_quality,
        color_temperature_k=plan.color_temperature_k,
        fill_level_percent=plan.fill_level_percent,
        exposure_intent=plan.exposure_intent,
        source_strategy=plan.source_strategy,
        shadow_strategy=plan.shadow_strategy,
        subject_readability=plan.subject_readability,
        separation_strategy=plan.separation_strategy,
        continuity_notes=plan.continuity_notes,
        lighting_constraints=plan.lighting_constraints,
        lighting_profile_asset_id="",
    )


def test_suggested_lighting_is_deterministic_grounded_and_renderer_neutral(tmp_path: Path) -> None:
    service, _shots, _assets, _camera_service = _service(tmp_path)

    plan = service.suggested_plan("EP-001-SCN-001-SHT-001")

    assert plan.lighting_intent is LightingIntent.NATURALISTIC
    assert plan.color_temperature_k == 5600
    assert plan.fill_level_percent == 18
    assert plan.exposure_intent is ExposureIntent.PROTECT_HIGHLIGHTS
    assert "motivated" in plan.source_strategy.lower()
    assert "glow" in plan.source_strategy.lower()


def test_lighting_planning_requires_a_current_ready_camera_plan(tmp_path: Path) -> None:
    service, shots, _assets, camera = _service(tmp_path)
    camera.camera_plan = replace(camera.camera_plan, status=CameraPlanStatus.DRAFT)

    with pytest.raises(GovernedLightingPlanningError, match="Ready governed Camera Plan"):
        service.create_suggested(shots.shot.shot_id)


def test_lighting_plan_persists_and_becomes_ready_with_current_context(tmp_path: Path) -> None:
    service, shots, _assets, _camera = _service(tmp_path)
    plan = service.create_suggested(shots.shot.shot_id)

    ready = service.mark_ready(plan.shot_id)

    assert ready.status is LightingPlanStatus.READY
    assert service.is_production_ready(ready)
    assert service.plan(plan.shot_id) == ready


def test_changed_camera_plan_makes_ready_lighting_plan_stale(tmp_path: Path) -> None:
    service, shots, _assets, camera = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    camera.camera_plan = replace(camera.camera_plan, focal_length_mm=35)

    assert not service.is_camera_context_current(ready)
    assert not service.is_production_ready(ready)


def test_changed_asset_context_makes_ready_lighting_plan_stale(tmp_path: Path) -> None:
    service, shots, assets, _camera = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    assets.binding = replace(assets.binding, asset_dependency_hash="asset-v2")

    assert not service.is_asset_context_current(ready)
    assert not service.is_production_ready(ready)


def test_ready_lighting_plan_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, shots, _assets, _camera = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    with pytest.raises(GovernedLightingPlanningError, match="return to Draft"):
        service.delete(ready.shot_id)

    draft = service.return_to_draft(ready.shot_id)
    assert draft.status is LightingPlanStatus.DRAFT
    refreshed = _refresh_draft(service, ready.shot_id)
    assert refreshed.status is LightingPlanStatus.DRAFT
    assert service.delete(ready.shot_id)
