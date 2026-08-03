"""Tests for production-container-aware StoryService behavior."""

from __future__ import annotations

import json
from pathlib import Path

from vscs.application.projects import ProjectService
from vscs.application.ssie import Scene
from vscs.application.story import ProductionContainerType, StoryService
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import DatabaseManager


def _open_project(tmp_path: Path) -> StoryService:
    configuration = ConfigurationService(tmp_path / "settings.yaml")
    configuration.load()
    projects = ProjectService(configuration, DatabaseManager())
    projects.create(tmp_path / "Project", name="Container Test")
    return StoryService(projects)


def _scene(scene_id: str, container_id: str, sequence: int) -> Scene:
    return Scene(
        scene_id=scene_id,
        episode_id=container_id,
        sequence_number=sequence,
        heading="EXT. XORIX ORBIT - DAY",
        location_asset_id="LOC-XORIX-ORBIT",
        summary="The production opens above Xorix.",
        scene_name="Opening View",
    )


def test_service_generates_container_aware_scene_ids(tmp_path: Path) -> None:
    stories = _open_project(tmp_path)

    assert stories.generate_container_scene_id(
        ProductionContainerType.EPISODE,
        "EP-001",
        2,
    ) == "EP-001-SCN-002"
    assert stories.generate_container_scene_id(
        ProductionContainerType.TRAILER,
        "T01",
        3,
    ) == "T01-SCN-003"


def test_service_tracks_sequence_per_container(tmp_path: Path) -> None:
    stories = _open_project(tmp_path)
    stories.save_scene(_scene("EP-001-SCN-001", "EP-001", 1))
    stories.save_scene(_scene("T01-SCN-001", "T01", 1))
    stories.save_scene(_scene("T01-SCN-002", "T01", 2))

    assert stories.next_sequence_number("EP-001") == 2
    assert stories.next_sequence_number("T01") == 3


def test_legacy_episode_scene_loads_as_episode_container(tmp_path: Path) -> None:
    stories = _open_project(tmp_path)
    stories.story_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.1",
        "scenes": [
            {
                "scene_id": "EP-001-SCN-001",
                "episode_id": "EP-001",
                "sequence_number": 1,
                "heading": "INT. BRIDGE - DAY",
                "location_asset_id": "LOC-BRIDGE",
                "summary": "The crew prepares to depart.",
                "transition_in": "cut",
            }
        ],
    }
    stories.story_file.write_text(json.dumps(payload), encoding="utf-8")

    scene = stories.list_scenes()[0]

    assert scene.episode_id == "EP-001"
    assert stories.container_type_for_scene(scene) is ProductionContainerType.EPISODE


def test_story_file_records_explicit_container_metadata(tmp_path: Path) -> None:
    stories = _open_project(tmp_path)
    stories.save_scene(_scene("T01-SCN-001", "T01", 1))

    payload = json.loads(stories.story_file.read_text(encoding="utf-8"))
    stored = payload["scenes"][0]

    assert payload["schema_version"] == "1.2"
    assert stored["container_type"] == "trailer"
    assert stored["container_id"] == "T01"
