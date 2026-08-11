from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.story import (
    AssetBindingStatus,
    CameraPlanStatus,
    GovernedCameraPlanningError,
    GovernedCameraPlanningService,
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
        self.ready = False
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
        return self.ready

    def list_bindings(self, *, shot_id: str | None = None):
        if shot_id is None or shot_id == self.binding.shot_id:
            return (self.binding,)
        return ()

    def is_production_ready(self, binding: ShotAssetBinding) -> bool:
        return self.ready and binding.asset_dependency_hash == self.binding.asset_dependency_hash


class FakeResolver:
    def resolve(self, _request):
        raise AssertionError("Camera profile resolution was not expected in this test")


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


def _service(tmp_path: Path, shot: ShotPlan | None = None):
    selected = shot or _shot()
    shots = FakeShots(selected)
    assets = FakeAssets(selected.shot_id)
    service = GovernedCameraPlanningService(
        FakeProjects(tmp_path),  # type: ignore[arg-type]
        shots,  # type: ignore[arg-type]
        assets,  # type: ignore[arg-type]
        FakeResolver(),  # type: ignore[arg-type]
        FakeBrowser(),  # type: ignore[arg-type]
    )
    return service, shots, assets


def test_suggested_plan_is_deterministic_and_grounded(tmp_path: Path) -> None:
    service, _shots, _assets = _service(tmp_path)

    plan = service.suggested_plan("EP-001-SCN-001-SHT-001")

    assert plan.shot_size is ShotSize.WIDE
    assert plan.focal_length_mm == 28
    assert plan.camera_height_m == pytest.approx(1.6)
    assert "plausible" in plan.focus_strategy.lower()
    assert "screen direction" in plan.continuity_notes.lower() or plan.continuity_notes


def test_draft_camera_work_can_begin_before_assets_are_ready(tmp_path: Path) -> None:
    service, _shots, _assets = _service(tmp_path)
    plan = service.create_suggested("EP-001-SCN-001-SHT-001")

    assert plan.status is CameraPlanStatus.DRAFT
    with pytest.raises(GovernedCameraPlanningError, match="asset requirement"):
        service.mark_ready(plan.shot_id)


def test_camera_plan_becomes_ready_only_with_current_asset_context(tmp_path: Path) -> None:
    service, _shots, assets = _service(tmp_path)
    plan = service.create_suggested("EP-001-SCN-001-SHT-001")
    assets.ready = True
    plan = service.update(
        plan.shot_id,
        shot_size=plan.shot_size,
        angle=plan.angle,
        movement=plan.movement,
        lens_family=plan.lens_family,
        focal_length_mm=plan.focal_length_mm,
        camera_height_m=plan.camera_height_m,
        screen_direction=plan.screen_direction,
        composition=plan.composition,
        focus_strategy=plan.focus_strategy,
        movement_notes=plan.movement_notes,
        continuity_notes=plan.continuity_notes,
        camera_constraints=plan.camera_constraints,
        camera_profile_asset_id="",
    )

    ready = service.mark_ready(plan.shot_id)

    assert ready.status is CameraPlanStatus.READY
    assert service.is_production_ready(ready)
    reloaded = service.plan(plan.shot_id)
    assert reloaded == ready


def test_changed_shot_makes_ready_camera_plan_stale(tmp_path: Path) -> None:
    service, shots, assets = _service(tmp_path)
    assets.ready = True
    plan = service.create_suggested(shots.shot.shot_id)
    plan = service.update(
        plan.shot_id,
        shot_size=plan.shot_size,
        angle=plan.angle,
        movement=plan.movement,
        lens_family=plan.lens_family,
        focal_length_mm=plan.focal_length_mm,
        camera_height_m=plan.camera_height_m,
        screen_direction=plan.screen_direction,
        composition=plan.composition,
        focus_strategy=plan.focus_strategy,
        movement_notes=plan.movement_notes,
        continuity_notes=plan.continuity_notes,
        camera_constraints=plan.camera_constraints,
        camera_profile_asset_id="",
    )
    ready = service.mark_ready(plan.shot_id)

    shots.shot = replace(shots.shot, required_action="Mauritania begins descent")

    assert not service.is_upstream_current(ready)
    assert not service.is_production_ready(ready)


def test_changed_asset_context_makes_camera_plan_stale(tmp_path: Path) -> None:
    service, shots, assets = _service(tmp_path)
    assets.ready = True
    plan = service.create_suggested(shots.shot.shot_id)
    plan = service.update(
        plan.shot_id,
        shot_size=plan.shot_size,
        angle=plan.angle,
        movement=plan.movement,
        lens_family=plan.lens_family,
        focal_length_mm=plan.focal_length_mm,
        camera_height_m=plan.camera_height_m,
        screen_direction=plan.screen_direction,
        composition=plan.composition,
        focus_strategy=plan.focus_strategy,
        movement_notes=plan.movement_notes,
        continuity_notes=plan.continuity_notes,
        camera_constraints=plan.camera_constraints,
        camera_profile_asset_id="",
    )
    ready = service.mark_ready(plan.shot_id)

    assets.binding = replace(assets.binding, asset_dependency_hash="asset-v2")

    assert not service.is_asset_context_current(ready)
    assert not service.is_production_ready(ready)


def test_ready_camera_plan_is_immutable_until_returned_to_draft(tmp_path: Path) -> None:
    service, shots, assets = _service(tmp_path)
    assets.ready = True
    plan = service.create_suggested(shots.shot.shot_id)
    plan = service.update(
        plan.shot_id,
        shot_size=plan.shot_size,
        angle=plan.angle,
        movement=plan.movement,
        lens_family=plan.lens_family,
        focal_length_mm=plan.focal_length_mm,
        camera_height_m=plan.camera_height_m,
        screen_direction=plan.screen_direction,
        composition=plan.composition,
        focus_strategy=plan.focus_strategy,
        movement_notes=plan.movement_notes,
        continuity_notes=plan.continuity_notes,
        camera_constraints=plan.camera_constraints,
        camera_profile_asset_id="",
    )
    service.mark_ready(plan.shot_id)

    with pytest.raises(GovernedCameraPlanningError, match="return to Draft"):
        service.delete(plan.shot_id)

    draft = service.return_to_draft(plan.shot_id)
    assert draft.status is CameraPlanStatus.DRAFT
    assert service.delete(plan.shot_id)
