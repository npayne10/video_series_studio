"""Real governed planner hash implementations must govern CAP evidence."""

import json

import pytest

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.governed_planning_evidence import (
    ProductionPlanningContracts,
    verified_governed_shot_evidence,
    verified_shots_to_spatial_sources,
)


def _write(root, name, key, rows):
    folder = root / "planning"
    folder.mkdir(exist_ok=True)
    (folder / name).write_text(json.dumps({key: rows}), encoding="utf-8")


def _project(root, binding_status="ready"):
    calculator = ProductionPlanningContracts()
    episode = {
        "episode_id": "EP-001",
        "story_id": "STORY-001",
        "sequence_number": 1,
        "title": "Episode",
        "story_scope": "Observation",
        "production_objective": "Show a quiet vessel",
        "target_runtime_seconds": 45,
        "status": "ready",
    }
    scene = {
        "scene_id": "EP-001-SCN-001",
        "episode_id": "EP-001",
        "sequence_number": 1,
        "title": "Engineering",
        "story_scope": "Observation",
        "production_objective": "Show engineering room",
        "target_runtime_seconds": 45,
        "setting_requirement": "Engineering Control Room",
        "required_events": ["Diagnostic pulse"],
        "status": "ready",
        "episode_contract_hash": calculator.episode_contract_hash(episode),
    }
    shot = {
        "shot_id": "EP-001-SCN-001-SHT-001",
        "scene_id": "EP-001-SCN-001",
        "sequence_number": 1,
        "title": "Console",
        "narrative_purpose": "Watch the console",
        "production_objective": "Show control room",
        "target_runtime_seconds": 15,
        "required_action": "Diagnostic Console inside Engineering Control Room.",
        "status": "ready",
        "scene_contract_hash": calculator.scene_contract_hash(scene),
    }
    binding = {
        "shot_id": "EP-001-SCN-001-SHT-001",
        "asset_id": "CAP-PRP-001",
        "status": binding_status,
        "shot_contract_hash": calculator.shot_contract_hash(shot),
    }
    _write(root, "episode_plans.json", "episodes", [episode])
    _write(root, "scene_plans.json", "scenes", [scene])
    _write(root, "shot_plans.json", "shots", [shot])
    _write(root, "asset_resolutions.json", "bindings", [binding])
    return episode, scene, shot


def test_real_planner_hashes_forward_ready_evidence(tmp_path):
    _project(tmp_path)
    verified = verified_governed_shot_evidence(tmp_path, "STORY-001", ProductionPlanningContracts())
    assert len(verified) == 1
    shots = verified_shots_to_spatial_sources(verified, selected_story_id="STORY-001")
    assert shots[0].shot_id == "EP-001-SCN-001-SHT-001"
    assert "required_action: Diagnostic Console inside" in shots[0].text
    assert not (tmp_path / "story").exists()


def test_real_planner_hash_rejects_changed_parent(tmp_path):
    episode, _scene, _shot = _project(tmp_path)
    episode["production_objective"] = "Changed upstream objective"
    _write(tmp_path, "episode_plans.json", "episodes", [episode])
    with pytest.raises(ShotTextAuthorityError, match="stale"):
        verified_governed_shot_evidence(tmp_path, "STORY-001", ProductionPlanningContracts())


def test_real_planner_hash_does_not_promote_draft_binding(tmp_path):
    _project(tmp_path, binding_status="draft")
    with pytest.raises(ShotTextAuthorityError, match="Draft"):
        verified_governed_shot_evidence(tmp_path, "STORY-001", ProductionPlanningContracts())
