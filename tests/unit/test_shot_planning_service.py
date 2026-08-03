"""Tests for Phase 17.2 persistent shot planning."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

from vscs.application.projects import ProjectService
from vscs.application.shots import (
    ProductionShot,
    ShotPlanningService,
    ShotPlanningStatus,
)
from vscs.application.ssie import (
    CameraMovement,
    LensFamily,
    LightingMood,
    ShotPurpose,
    ShotSize,
)
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


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


def _shot(shot_id: str, sequence: int, title: str) -> ProductionShot:
    return ProductionShot(
        shot_id=shot_id,
        scene_id="EP-001-SCN-001",
        sequence_number=sequence,
        title=title,
        description=f"Production description for {title}.",
        estimated_duration_seconds=6.0,
    )


def test_shot_service_persists_replaces_and_deletes(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    service = ShotPlanningService(context.services.require(ProjectService))

    first = _shot("EP-001-SCN-001-SHT-001", 1, "Establishing bridge")
    service.save_shot(first)
    assert service.list_shots("EP-001-SCN-001") == (first,)

    replacement = replace(first, title="Revised bridge establishing")
    service.save_shot(replacement)
    assert service.shot(first.shot_id) == replacement
    assert service.delete_shot(first.shot_id)
    assert service.list_shots() == ()
    context.shutdown()


def test_shot_service_generates_identity_and_reorders(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    service = ShotPlanningService(context.services.require(ProjectService))
    first = _shot("EP-001-SCN-001-SHT-001", 1, "Master")
    second = _shot("EP-001-SCN-001-SHT-002", 2, "Reaction")
    service.save_shot(first)
    service.save_shot(second)

    assert service.next_sequence_number(first.scene_id) == 3
    assert service.generate_shot_id(first.scene_id, 3).endswith("SHT-003")
    ordered = service.reorder_scene(first.scene_id, (second.shot_id, first.shot_id))
    assert [shot.shot_id for shot in ordered] == [second.shot_id, first.shot_id]
    assert [shot.sequence_number for shot in ordered] == [1, 2]
    context.shutdown()


def test_shot_service_rejects_invalid_shot(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    service = ShotPlanningService(context.services.require(ProjectService))

    with pytest.raises(ValueError, match="title"):
        service.save_shot(
            ProductionShot(
                shot_id="EP-001-SCN-001-SHT-001",
                scene_id="EP-001-SCN-001",
                sequence_number=1,
                title="",
                description="Description",
            )
        )
    context.shutdown()


def test_shot_service_tolerates_string_backed_enum_values(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    service = ShotPlanningService(context.services.require(ProjectService))
    shot = _shot("EP-001-SCN-001-SHT-001", 1, "Defensive serialization")
    string_backed = replace(
        shot,
        purpose=cast(Any, ShotPurpose.COVERAGE.value),
        shot_size=cast(Any, ShotSize.MEDIUM.value),
        camera_movement=cast(Any, CameraMovement.STATIC.value),
        lens_family=cast(Any, LensFamily.NORMAL.value),
        lighting_mood=cast(Any, LightingMood.NATURALISTIC.value),
        status=cast(Any, ShotPlanningStatus.READY.value),
    )

    service.save_shot(string_backed)
    restored = service.list_shots()[0]

    assert restored.purpose is ShotPurpose.COVERAGE
    assert restored.shot_size is ShotSize.MEDIUM
    assert restored.camera_movement is CameraMovement.STATIC
    assert restored.lens_family is LensFamily.NORMAL
    assert restored.lighting_mood is LightingMood.NATURALISTIC
    assert restored.status is ShotPlanningStatus.READY
    context.shutdown()
