from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest

from vscs.application.story import (
    AssetBindingStatus,
    AtmosphereState,
    CameraAngle,
    CameraMovement,
    CameraPlan,
    CameraPlanStatus,
    EnvironmentContext,
    EnvironmentPlanStatus,
    ExposureIntent,
    GovernedEnvironmentPlanningError,
    GovernedEnvironmentPlanningService,
    KeyDirection,
    LensFamily,
    LightingIntent,
    LightingPlan,
    LightingPlanStatus,
    LightQuality,
    ScenePlan,
    ScenePlanStatus,
    ScreenDirection,
    ShotAssetBinding,
    ShotPlan,
    ShotPlanStatus,
    ShotSize,
    TimeContext,
    WeatherState,
)
from vscs.domain.assets import AssetCategory


@dataclass
class FakeProjects:
    project_directory: Path


class FakeScenes:
    def __init__(self, scene: ScenePlan) -> None:
        self.scene = scene

    def plan(self, scene_id: str) -> ScenePlan | None:
        return self.scene if scene_id.strip().upper() == self.scene.scene_id else None


class FakeShots:
    def __init__(self, shot: ShotPlan) -> None:
        self.shot = shot

    def plan(self, shot_id: str) -> ShotPlan | None:
        return self.shot if shot_id.strip().upper() == self.shot.shot_id else None

    def is_production_ready(self, shot: ShotPlan) -> bool:
        return shot.status is ShotPlanStatus.READY and shot == self.shot


class FakeAssets:
    def __init__(self, shot_id: str) -> None:
        self.ready = True
        self.binding = ShotAssetBinding(
            binding_id=f"{shot_id}-AST-001",
            shot_id=shot_id,
            sequence_number=1,
            role="Primary spacecraft",
            requirement="Mauritania",
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


class FakeLighting:
    def __init__(self, plan: LightingPlan) -> None:
        self.lighting_plan = plan

    def plan(self, shot_id: str) -> LightingPlan | None:
        return self.lighting_plan if shot_id.strip().upper() == self.lighting_plan.shot_id else None

    def is_production_ready(self, plan: LightingPlan) -> bool:
        return plan.status is LightingPlanStatus.READY and plan == self.lighting_plan


def _scene(setting: str = "Xorix orbit") -> ScenePlan:
    return ScenePlan(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        title="Arrival at Xorix",
        story_scope="Arrival in orbit",
        production_objective="Establish Xorix and spacecraft scale",
        target_runtime_seconds=60,
        setting_requirement=setting,
        required_events=("Mauritania arrives",),
        continuity_in="Interstellar transit complete",
        continuity_out="Orbital insertion established",
        episode_contract_hash="episode",
        status=ScenePlanStatus.READY,
    )


def _shot() -> ShotPlan:
    return ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Orbital arrival",
        narrative_purpose="Establish Xorix",
        production_objective="Show physically credible orbital scale",
        target_runtime_seconds=12,
        required_action="Mauritania crosses the frame in stable orbit",
        continuity_in="Ship emerges from transit",
        continuity_out="Stable orbit established",
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
        movement_notes="Stable tracking motion",
        continuity_notes="Preserve screen direction",
        shot_contract_hash="shot",
        asset_context_hash="asset",
        status=CameraPlanStatus.READY,
    )


def _lighting(shot_id: str) -> LightingPlan:
    return LightingPlan(
        lighting_plan_id=f"{shot_id}-LGT",
        shot_id=shot_id,
        lighting_intent=LightingIntent.NATURALISTIC,
        key_direction=KeyDirection.SIDE,
        key_quality=LightQuality.HARD,
        color_temperature_k=5600,
        fill_level_percent=18,
        exposure_intent=ExposureIntent.PROTECT_HIGHLIGHTS,
        source_strategy="One physically motivated dominant source",
        shadow_strategy="Preserve credible directional shadows",
        subject_readability="Keep spacecraft geometry readable",
        shot_contract_hash="shot",
        asset_context_hash="asset",
        camera_context_hash="camera",
        status=LightingPlanStatus.READY,
    )


def _service(tmp_path: Path, *, setting: str = "Xorix orbit"):
    scene = _scene(setting)
    shot = _shot()
    scenes = FakeScenes(scene)
    shots = FakeShots(shot)
    assets = FakeAssets(shot.shot_id)
    camera = FakeCamera(_camera(shot.shot_id))
    lighting = FakeLighting(_lighting(shot.shot_id))
    service = GovernedEnvironmentPlanningService(
        FakeProjects(tmp_path),  # type: ignore[arg-type]
        scenes,  # type: ignore[arg-type]
        shots,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        camera,  # type: ignore[arg-type]
        lighting,  # type: ignore[arg-type]
    )
    return service, scenes, shots, assets, camera, lighting


def _refresh_draft(service: GovernedEnvironmentPlanningService, shot_id: str):
    plan = service.plan(shot_id)
    assert plan is not None
    return service.update(
        shot_id,
        environment_context=plan.environment_context,
        time_context=plan.time_context,
        atmosphere_state=plan.atmosphere_state,
        weather_state=plan.weather_state,
        gravity_m_s2=plan.gravity_m_s2,
        pressure_kpa=plan.pressure_kpa,
        temperature_c=plan.temperature_c,
        visibility_m=plan.visibility_m,
        surface_state=plan.surface_state,
        environmental_motion=plan.environmental_motion,
        hazard_notes=plan.hazard_notes,
        continuity_notes=plan.continuity_notes,
        environment_constraints=plan.environment_constraints,
    )


def test_orbital_suggestion_enforces_vacuum_without_invented_planet_physics(tmp_path: Path) -> None:
    service, *_rest = _service(tmp_path)

    plan = service.suggested_plan("EP-001-SCN-001-SHT-001")

    assert plan.environment_context is EnvironmentContext.ORBITAL_SPACE
    assert plan.atmosphere_state is AtmosphereState.VACUUM
    assert plan.weather_state is WeatherState.NONE
    assert plan.pressure_kpa == 0.0
    assert plan.gravity_m_s2 is None
    assert plan.temperature_c is None
    assert "haze" in " ".join(plan.environment_constraints).lower()


def test_surface_suggestion_keeps_unknown_xorix_physics_unknown(tmp_path: Path) -> None:
    service, *_rest = _service(tmp_path, setting="Xorix forest surface at dusk")

    plan = service.suggested_plan("EP-001-SCN-001-SHT-001")

    assert plan.environment_context is EnvironmentContext.EXTERIOR_SURFACE
    assert plan.time_context is TimeContext.DUSK
    assert plan.atmosphere_state is AtmosphereState.UNKNOWN
    assert plan.gravity_m_s2 is None
    assert plan.pressure_kpa is None
    assert plan.temperature_c is None


def test_environment_planning_requires_current_ready_lighting(tmp_path: Path) -> None:
    service, _scenes, shots, _assets, _camera, lighting = _service(tmp_path)
    lighting.lighting_plan = replace(lighting.lighting_plan, status=LightingPlanStatus.DRAFT)

    with pytest.raises(GovernedEnvironmentPlanningError, match="Ready governed Lighting Plan"):
        service.create_suggested(shots.shot.shot_id)


def test_environment_plan_persists_and_becomes_ready_with_current_context(tmp_path: Path) -> None:
    service, _scenes, shots, _assets, _camera, _lighting = _service(tmp_path)
    plan = service.create_suggested(shots.shot.shot_id)

    ready = service.mark_ready(plan.shot_id)

    assert ready.status is EnvironmentPlanStatus.READY
    assert service.is_production_ready(ready)
    assert service.plan(plan.shot_id) == ready


def test_changed_shot_makes_ready_environment_plan_stale(tmp_path: Path) -> None:
    service, _scenes, shots, _assets, _camera, _lighting = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    shots.shot = replace(shots.shot, required_action="Mauritania rolls during orbital insertion")

    assert not service.is_shot_context_current(ready)
    assert not service.is_production_ready(ready)


def test_changed_asset_binding_makes_ready_environment_plan_stale(tmp_path: Path) -> None:
    service, _scenes, shots, assets, _camera, _lighting = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    assets.binding = replace(assets.binding, asset_dependency_hash="asset-v2")

    assert not service.is_asset_context_current(ready)
    assert not service.is_production_ready(ready)


def test_changed_camera_makes_ready_environment_plan_stale(tmp_path: Path) -> None:
    service, _scenes, shots, _assets, camera, _lighting = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    camera.camera_plan = replace(camera.camera_plan, focal_length_mm=35)

    assert not service.is_camera_context_current(ready)
    assert not service.is_production_ready(ready)


def test_changed_lighting_makes_ready_environment_plan_stale(tmp_path: Path) -> None:
    service, _scenes, shots, _assets, _camera, lighting = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    lighting.lighting_plan = replace(lighting.lighting_plan, fill_level_percent=25)

    assert not service.is_lighting_context_current(ready)
    assert not service.is_production_ready(ready)


def test_ready_environment_is_immutable_and_rejects_impossible_vacuum_weather(
    tmp_path: Path,
) -> None:
    service, _scenes, shots, _assets, _camera, _lighting = _service(tmp_path)
    ready = service.mark_ready(service.create_suggested(shots.shot.shot_id).shot_id)

    with pytest.raises(GovernedEnvironmentPlanningError, match="return to Draft"):
        service.delete(ready.shot_id)

    draft = service.return_to_draft(ready.shot_id)
    assert draft.status is EnvironmentPlanStatus.DRAFT
    with pytest.raises(GovernedEnvironmentPlanningError, match="weather"):
        service.update(
            draft.shot_id,
            environment_context=EnvironmentContext.ORBITAL_SPACE,
            time_context=TimeContext.NOT_APPLICABLE,
            atmosphere_state=AtmosphereState.VACUUM,
            weather_state=WeatherState.STORM,
            gravity_m_s2=None,
            pressure_kpa=0.0,
            temperature_c=None,
            visibility_m=None,
            surface_state="vacuum",
            environmental_motion="orbital motion only",
            hazard_notes="",
            continuity_notes="",
            environment_constraints=(),
        )

    refreshed = _refresh_draft(service, ready.shot_id)
    assert refreshed.status is EnvironmentPlanStatus.DRAFT
    assert service.delete(ready.shot_id)
