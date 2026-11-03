"""B.5.21A — offline governed CAP context provenance and scope acceptance."""

import json
from dataclasses import asdict, replace

import pytest

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.context_preparation import prepare_cap_context
from vscs.application.caps.governed_planning_evidence import ProductionPlanningContracts
from vscs.application.story.asset_resolver import AssetBindingStatus, ShotAssetBinding
from vscs.application.story.episode_planning import EpisodePlan, EpisodePlanStatus
from vscs.application.story.scene_planning import ScenePlan, ScenePlanStatus
from vscs.application.story.shot_planning import ShotPlan, ShotPlanStatus
from vscs.domain.assets.models import AssetCategory


def _write(root, name, key, records):
    path = root / "planning" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: records}), encoding="utf-8")


def _fixture(root):
    contracts = ProductionPlanningContracts()
    episode = EpisodePlan(
        episode_id="EP-001", story_id="STORY-001", sequence_number=1,
        title="Audit", story_scope="Engineering", production_objective="Observe",
        target_runtime_seconds=15, status=EpisodePlanStatus.READY,
    )
    scene = ScenePlan(
        scene_id="EP-001-SCN-001", episode_id=episode.episode_id, sequence_number=1,
        title="Control room", story_scope="Room", production_objective="Observe console",
        target_runtime_seconds=15, setting_requirement="Control room",
        required_events=("Console steady",),
        episode_contract_hash=contracts.episode_contract_hash(asdict(episode)),
        status=ScenePlanStatus.READY,
    )
    shot = ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001", scene_id=scene.scene_id, sequence_number=1,
        title="Quiet console", narrative_purpose="Quiet console",
        production_objective="Observe", target_runtime_seconds=15,
        required_action="In the engineering control room, the diagnostic console glows.",
        scene_contract_hash=contracts.scene_contract_hash(asdict(scene)),
        status=ShotPlanStatus.READY,
    )
    bindings = [
        ShotAssetBinding(
            binding_id=f"{shot.shot_id}-AST-{index:03d}",
            shot_id=shot.shot_id, sequence_number=index, role="required",
            requirement=name, expected_category=category,
            asset_id=asset_id,
            shot_contract_hash=contracts.shot_contract_hash(asdict(shot)),
            status=AssetBindingStatus.READY,
        )
        for index, name, category, asset_id in (
            (1, "Engineering control room", AssetCategory.LOCATION, "CAP-LOC-001"),
            (2, "Diagnostic console", AssetCategory.PROP, "CAP-PRP-001"),
        )
    ]
    _write(root, "episode_plans.json", "episodes", [asdict(episode)])
    _write(root, "scene_plans.json", "scenes", [asdict(scene)])
    _write(root, "shot_plans.json", "shots", [asdict(shot)])
    _write(root, "asset_resolutions.json", "bindings", [asdict(b) for b in bindings])
    return shot, bindings


def _prepare(root, story_id="STORY-001", asset_id="CAP-LOC-001"):
    return prepare_cap_context(
        root, story_id, asset_id, "An approved vessel has a control room.",
        "approved-story-fingerprint", "registered-asset-fingerprint",
    )


def test_verified_context_manifest_has_attributed_source_and_stable_fingerprint(tmp_path):
    _fixture(tmp_path)
    manifest = _prepare(tmp_path)
    assert manifest.story_id == "STORY-001"
    assert manifest.asset_id == "CAP-LOC-001"
    assert manifest.sources[0].authority == "approved_story_context"
    assert any(item.authority == "verified_ready_shot" for item in manifest.sources)
    assert any(item.record_id == "EP-001-SCN-001-SHT-001" for item in manifest.sources)
    assert manifest.fingerprint == _prepare(tmp_path).fingerprint


def test_draft_binding_is_discovered_but_shot_context_is_unverified(tmp_path):
    _shot, bindings = _fixture(tmp_path)
    bindings[1] = replace(bindings[1], status=AssetBindingStatus.DRAFT)
    _write(tmp_path, "asset_resolutions.json", "bindings", [asdict(b) for b in bindings])
    manifest = _prepare(tmp_path)
    assert any(item.authority == "unverified_shot" for item in manifest.sources)
    assert not any(item.authority == "verified_ready_shot" for item in manifest.sources)
    assert any("Draft or missing bindings" in warning for warning in manifest.warnings)
    assert manifest.sources[0].authority == "approved_story_context"


def test_tampered_shot_text_invalidates_verified_context(tmp_path):
    shot, _bindings = _fixture(tmp_path)
    changed = asdict(shot)
    changed["required_action"] = "Unapproved story change"
    _write(tmp_path, "shot_plans.json", "shots", [changed])
    manifest = _prepare(tmp_path)
    assert not any(item.authority == "verified_ready_shot" for item in manifest.sources)
    assert any("stale or inconsistent" in warning for warning in manifest.warnings)


def test_wrong_story_and_wrong_asset_cannot_reuse_context(tmp_path):
    _fixture(tmp_path)
    with pytest.raises((ValueError, ShotTextAuthorityError)):
        _prepare(tmp_path, story_id="STORY-OTHER")
    with pytest.raises(ValueError, match="no governed Shot binding"):
        _prepare(tmp_path, asset_id="CAP-PRP-OTHER")
