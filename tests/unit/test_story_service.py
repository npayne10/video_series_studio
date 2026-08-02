"""Tests for project-backed structured story storage and SSIE planning."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene, SceneTransition
from vscs.application.story import StoryService
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import DatabaseManager


def _service(tmp_path: Path) -> StoryService:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration, DatabaseManager())
    projects.create(tmp_path / "Project", name="Project")
    return StoryService(projects)


def _scene(scene_id: str = "SCN-001", sequence: int = 1) -> Scene:
    return Scene(
        scene_id=scene_id,
        episode_id="EP-001",
        sequence_number=sequence,
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="James confronts an unexplained signal beyond the ship.",
        participant_asset_ids=("CHR-JAMES",),
        dialogue=("That signal should not be there.",),
        required_asset_ids=("PROP-CONSOLE",),
        time_of_day="night",
        transition_in=SceneTransition.CUT,
        estimated_duration_seconds=24.0,
    )


def test_story_service_persists_and_orders_scenes(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service.save_scene(_scene("SCN-002", 2))
    service.save_scene(_scene("SCN-001", 1))

    assert [scene.scene_id for scene in service.list_scenes()] == ["SCN-001", "SCN-002"]
    assert service.story_file.is_file()


def test_story_service_replaces_and_deletes_scenes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.save_scene(_scene())
    service.save_scene(replace(_scene(), summary="A revised structured summary."))

    stored = service.scene("SCN-001")
    assert stored is not None
    assert stored.summary == "A revised structured summary."
    assert service.delete_scene("SCN-001") is True
    assert service.list_scenes() == ()


def test_story_service_generates_enriched_ssie_plan(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.save_scene(_scene())

    plan = service.plan_scene("SCN-001")

    assert plan.scene.scene_id == "SCN-001"
    assert plan.shots
    assert all(shot.camera_plan is not None for shot in plan.shots)
    assert all(shot.lighting_plan is not None for shot in plan.shots)
    assert all(shot.blocking_plan is not None for shot in plan.shots)
    assert all(shot.continuity_plan is not None for shot in plan.shots)
    assert service.plan("SCN-001") is plan
