"""B.5.21A — offline governed CAP context provenance and scope acceptance."""

import json
from dataclasses import asdict, replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.authoritative_shot_text import ShotTextAuthorityError
from vscs.application.caps.context_preparation import (
    CAPContextManifest,
    CAPContextSource,
    prepare_cap_context,
)
from vscs.application.caps.governed_planning_evidence import ProductionPlanningContracts
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.story_batch import StoryCAPBatchService
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.story.asset_resolver import AssetBindingStatus, ShotAssetBinding
from vscs.application.story.episode_planning import EpisodePlan, EpisodePlanStatus
from vscs.application.story.lifecycle import StoryRecord, StoryStatus
from vscs.application.story.scene_planning import ScenePlan, ScenePlanStatus
from vscs.application.story.shot_planning import ShotPlan, ShotPlanStatus
from vscs.domain.assets.models import Asset, AssetCategory
from vscs.presentation.dialogs import story_cap_batch_dialog as batch_ui


def _write(root, name, key, records):
    path = root / "planning" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: records}), encoding="utf-8")


def _fixture(root):
    contracts = ProductionPlanningContracts()
    episode = EpisodePlan(
        episode_id="EP-001",
        story_id="STORY-001",
        sequence_number=1,
        title="Audit",
        story_scope="Engineering",
        production_objective="Observe",
        target_runtime_seconds=15,
        status=EpisodePlanStatus.READY,
    )
    scene = ScenePlan(
        scene_id="EP-001-SCN-001",
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Control room",
        story_scope="Room",
        production_objective="Observe console",
        target_runtime_seconds=15,
        setting_requirement="Control room",
        required_events=("Console steady",),
        episode_contract_hash=contracts.episode_contract_hash(asdict(episode)),
        status=ScenePlanStatus.READY,
    )
    shot = ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Quiet console",
        narrative_purpose="Quiet console",
        production_objective="Observe",
        target_runtime_seconds=15,
        required_action="In the engineering control room, the diagnostic console glows.",
        scene_contract_hash=contracts.scene_contract_hash(asdict(scene)),
        status=ShotPlanStatus.READY,
    )
    bindings = [
        ShotAssetBinding(
            binding_id=f"{shot.shot_id}-AST-{index:03d}",
            shot_id=shot.shot_id,
            sequence_number=index,
            role="required",
            requirement=name,
            expected_category=category,
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
        root,
        story_id,
        asset_id,
        "An approved vessel has a control room.",
        "approved-story-fingerprint",
        "registered-asset-fingerprint",
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


def test_duplicate_plan_ids_are_rejected_before_context_promotion(tmp_path):
    _fixture(tmp_path)
    path = tmp_path / "planning" / "episode_plans.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["episodes"].append(dict(payload["episodes"][0]))
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ShotTextAuthorityError, match="Ambiguous planning ownership"):
        _prepare(tmp_path)


def test_story_scoped_batch_discovery_excludes_foreign_assets(tmp_path):
    shot, _bindings = _fixture(tmp_path)
    episode_two = EpisodePlan(
        episode_id="EP-002",
        story_id="STORY-002",
        sequence_number=1,
        title="Second Story",
        story_scope="Different vessel",
        production_objective="Another room",
        target_runtime_seconds=15,
        status=EpisodePlanStatus.READY,
    )
    contracts = ProductionPlanningContracts()
    ep_path = tmp_path / "planning" / "episode_plans.json"
    episodes = json.loads(ep_path.read_text(encoding="utf-8"))["episodes"]
    episodes.append(asdict(episode_two))
    _write(tmp_path, "episode_plans.json", "episodes", episodes)
    scene_two = ScenePlan(
        scene_id="EP-002-SCN-001",
        episode_id=episode_two.episode_id,
        sequence_number=1,
        title="Elsewhere",
        story_scope="Other",
        production_objective="Other",
        target_runtime_seconds=15,
        setting_requirement="Foreign room",
        required_events=("Another event",),
        episode_contract_hash=contracts.episode_contract_hash(asdict(episode_two)),
        status=ScenePlanStatus.READY,
    )
    sc_path = tmp_path / "planning" / "scene_plans.json"
    scenes = json.loads(sc_path.read_text(encoding="utf-8"))["scenes"]
    scenes.append(asdict(scene_two))
    _write(tmp_path, "scene_plans.json", "scenes", scenes)
    foreign = replace(
        shot,
        shot_id="EP-002-SCN-001-SHT-001",
        scene_id=scene_two.scene_id,
        scene_contract_hash=contracts.scene_contract_hash(asdict(scene_two)),
    )
    sh_path = tmp_path / "planning" / "shot_plans.json"
    shots = json.loads(sh_path.read_text(encoding="utf-8"))["shots"]
    shots.append(asdict(foreign))
    _write(tmp_path, "shot_plans.json", "shots", shots)
    ledger = tmp_path / "planning" / "asset_resolutions.json"
    bindings = json.loads(ledger.read_text(encoding="utf-8"))["bindings"]
    bindings.append(
        {
            "shot_id": foreign.shot_id,
            "asset_id": "CAP-LOC-OTHER",
            "expected_category": "location",
            "status": "ready",
            "shot_contract_hash": contracts.shot_contract_hash(asdict(foreign)),
        }
    )
    _write(tmp_path, "asset_resolutions.json", "bindings", bindings)

    assets = (
        Asset.model_construct(
            asset_id="CAP-LOC-001",
            name="Engineering control room",
            category=AssetCategory.LOCATION,
            description="",
        ),
        Asset.model_construct(
            asset_id="CAP-PRP-001",
            name="Diagnostic console",
            category=AssetCategory.PROP,
            description="",
        ),
        Asset.model_construct(
            asset_id="CAP-LOC-OTHER",
            name="Foreign control room",
            category=AssetCategory.LOCATION,
            description="",
        ),
    )
    project = SimpleNamespace(project_directory=tmp_path, is_project_open=True)
    asset_service = SimpleNamespace(projects=project, list=lambda: assets)

    def missing(_asset_id):
        raise CAPNotFoundError("Not registered")

    spec_service = SimpleNamespace(caps=SimpleNamespace(get=missing))
    generator = SimpleNamespace(
        generator=SimpleNamespace(assets=asset_service), specifications=spec_service
    )
    story_service = SimpleNamespace(
        story=lambda story_id: StoryRecord(
            story_id=story_id,
            title="Approved",
            description="A real Story.",
            status=StoryStatus.APPROVED,
        ),
    )
    review = StoryCAPBatchReviewService(StoryCAPBatchService(story_service, generator))
    selected = review.discover("STORY-001")
    assert {item.asset_id for item in selected} == {"CAP-LOC-001", "CAP-PRP-001"}
    assert "CAP-LOC-OTHER" not in {item.asset_id for item in selected}


def test_context_button_is_read_only_and_story_switch_clears_selection(
    tmp_path, monkeypatch, qtbot
):
    approved = StoryRecord(
        story_id="STORY-001",
        title="Quiet Console",
        description="A governed control room",
        status=StoryStatus.APPROVED,
    )
    monkeypatch.setattr(
        batch_ui,
        "StoryLifecycleService",
        lambda _projects: SimpleNamespace(list_stories=lambda: (approved,)),
    )
    project = SimpleNamespace(project_directory=tmp_path, is_project_open=True)
    asset_service = SimpleNamespace(projects=project)
    caps = SimpleNamespace(assets=asset_service)
    generator = SimpleNamespace(caps=caps)
    dialog = batch_ui.StoryCAPBatchDialog(generator)
    qtbot.addWidget(dialog)
    dialog.assets.addItem("CAP-LOC-001", "CAP-LOC-001")
    dialog.context_button.setEnabled(True)
    source = CAPContextSource(
        "approved_story",
        "STORY-001",
        "description",
        "A governed control room",
        "approved_story_context",
        "source-hash",
    )
    manifest = CAPContextManifest(
        "STORY-001",
        "CAP-LOC-001",
        "story-hash",
        "asset-hash",
        (source,),
        (),
        "manifest-hash",
    )
    dialog.review_service = SimpleNamespace(
        prepare_context=lambda story_id, asset_id: (
            manifest if (story_id, asset_id) == ("STORY-001", "CAP-LOC-001") else None
        )
    )
    with patch.object(QMessageBox, "information") as notice:
        dialog.context_button.click()
    assert "Offline inspection only" in dialog.summary.toPlainText()
    assert "approved_story_context" in dialog.summary.toPlainText()
    assert "manifest-hash" in notice.call_args.args[2]
    dialog.story.addItem("STORY-002", "STORY-002")
    dialog.story.setCurrentIndex(1)
    assert dialog.assets.count() == 0
    assert not dialog.context_button.isEnabled()
