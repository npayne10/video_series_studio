"""Checkpoint 4B.4.1: independent immutable planning-snapshot authority."""

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from vscs.application.episode_planning_snapshot import (
    JsonPlanningSnapshotRepository,
    build_planning_snapshot,
    resolve_current_planning_snapshot,
)


def _services(shot_id="SHT-001"):
    @dataclass(frozen=True)
    class Episode:
        episode_id: str = "EP-001"
        story_id: str = "STORY-1"
        title: str = "Pilot"
        production_ready: bool = True

    @dataclass(frozen=True)
    class Scene:
        scene_id: str = "SCN-001"
        episode_id: str = "EP-001"

    @dataclass(frozen=True)
    class Shot:
        shot_id: str
        scene_id: str = "SCN-001"

    episode = Episode()
    scene = Scene()
    shot = Shot(shot_id)
    episodes, scenes, shots, reviews = Mock(), Mock(), Mock(), Mock()
    episodes.plan.return_value = episode
    scenes.list_plans.return_value = (scene,)
    scenes.is_production_ready.return_value = True
    shots.list_plans.return_value = (shot,)
    return episodes, scenes, shots, reviews


def test_snapshot_requires_single_persisted_production_identity():
    with pytest.raises(ValueError, match="production identity"):
        build_planning_snapshot("EP-001", _services(), (), "operator")


def test_snapshot_requires_operator_and_scene_authority():
    with pytest.raises(ValueError, match="operator identity"):
        build_planning_snapshot("EP-001", _services(), ("PROD-1",), "")
    services = _services()
    services[1].is_production_ready.return_value = False
    with pytest.raises(ValueError, match="Scene planning authority"):
        build_planning_snapshot("EP-001", services, ("PROD-1",), "operator")


def test_snapshot_publishes_once_and_rejects_changed_plan(tmp_path):
    services = _services()
    snapshot = build_planning_snapshot("EP-001", services, ("PROD-1",), "operator")
    repository = JsonPlanningSnapshotRepository(tmp_path)
    repository.create(snapshot)
    with pytest.raises(ValueError, match="already exists"):
        repository.create(snapshot)
    scope = resolve_current_planning_snapshot(
        tmp_path, "EP-001", services, ("PROD-1",), ("SHT-001",)
    )
    assert scope == snapshot.scope
    with pytest.raises(ValueError, match="Shot order"):
        resolve_current_planning_snapshot(tmp_path, "EP-001", services, ("PROD-1",), ("SHT-002",))
    with pytest.raises(ValueError, match="Shot order"):
        resolve_current_planning_snapshot(
            tmp_path, "EP-001", _services("SHT-002"), ("PROD-1",), ("SHT-001",)
        )


def test_snapshot_rejects_tampering(tmp_path):
    services = _services()
    snapshot = build_planning_snapshot("EP-001", services, ("PROD-1",), "operator")
    repository = JsonPlanningSnapshotRepository(tmp_path)
    path = repository.create(snapshot)
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["snapshot"]["production_id"] = "PROD-FORGED"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        repository.get("EP-001", snapshot.revision_id)
