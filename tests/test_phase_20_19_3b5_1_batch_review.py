"""Phase 20.19.3B.5.1 asset discovery and missing Draft CAP review gates."""

import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.governed_planning_evidence import ProductionPlanningContracts
from vscs.application.caps.story_batch import StoryBatchError
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.story.episode_planning import EpisodePlan, EpisodePlanStatus
from vscs.application.story.lifecycle import StoryRecord, StoryStatus
from vscs.application.story.scene_planning import ScenePlan, ScenePlanStatus
from vscs.application.story.shot_planning import ShotPlan, ShotPlanStatus
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus


@pytest.fixture
def review(tmp_path: Path):
    planning = tmp_path / "planning"
    planning.mkdir()
    contracts = ProductionPlanningContracts()
    episode = EpisodePlan(
        episode_id="EP-001",
        story_id="STORY-001",
        sequence_number=1,
        title="Test",
        story_scope="Control room",
        production_objective="Observe",
        target_runtime_seconds=15,
        status=EpisodePlanStatus.READY,
    )
    scene = ScenePlan(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        title="Test scene",
        story_scope="Control room",
        production_objective="Observe",
        target_runtime_seconds=15,
        setting_requirement="Control room",
        required_events=("Console",),
        episode_contract_hash=contracts.episode_contract_hash(asdict(episode)),
        status=ScenePlanStatus.READY,
    )
    shot = ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Test shot",
        narrative_purpose="Observe",
        production_objective="Show the control room",
        target_runtime_seconds=15,
        required_action="The console remains in the room.",
        scene_contract_hash=contracts.scene_contract_hash(asdict(scene)),
        status=ShotPlanStatus.READY,
    )
    for name, key, record in (
        ("episode_plans.json", "episodes", episode),
        ("scene_plans.json", "scenes", scene),
        ("shot_plans.json", "shots", shot),
    ):
        (planning / name).write_text(json.dumps({key: [asdict(record)]}), encoding="utf-8")
    shot_hash = contracts.shot_contract_hash(asdict(shot))
    (planning / "asset_resolutions.json").write_text(
        json.dumps(
            {
                "bindings": [
                    {
                        "shot_id": shot.shot_id,
                        "shot_contract_hash": shot_hash,
                        "asset_id": "CAP-LOC-001",
                        "expected_category": "location",
                    },
                    {
                        "shot_id": shot.shot_id,
                        "shot_contract_hash": shot_hash,
                        "asset_id": "CAP-LOC-001",
                        "expected_category": "location",
                    },
                    {
                        "shot_id": shot.shot_id,
                        "shot_contract_hash": shot_hash,
                        "asset_id": "CAP-PRP-001",
                        "expected_category": "prop",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    assets = Mock()
    assets.projects.project_directory = tmp_path
    assets.projects.is_project_open = True
    assets.list.return_value = (
        SimpleNamespace(
            asset_id="CAP-LOC-001", name="Control Room", category=AssetCategory.LOCATION
        ),
        SimpleNamespace(asset_id="CAP-PRP-001", name="Console", category=AssetCategory.PROP),
    )
    caps = Mock()
    from vscs.application.caps.service import CAPNotFoundError

    caps.get.side_effect = CAPNotFoundError("missing")
    batch = Mock()
    batch.stories.list_stories.return_value = (
        StoryRecord(
            story_id="STORY-001",
            title="Approved test",
            description="A governed room.",
            status=StoryStatus.APPROVED,
        ),
    )
    batch.current_story_fingerprint.return_value = "approved-story"
    batch.generator.generator.assets = assets
    batch.generator.specifications.caps = caps
    batch.generator.specifications.get.return_value = None
    return StoryCAPBatchReviewService(batch), caps, assets


def test_discovery_deduplicates_registered_bound_assets(review):
    service, _, _ = review
    discovered = service.discover("STORY-001")
    assert [x.asset_id for x in discovered] == ["CAP-LOC-001", "CAP-PRP-001"]
    assert all(not x.has_cap for x in discovered)


def test_discovery_rejects_category_collision(review):
    service, _, assets = review
    assets.list.return_value = (
        SimpleNamespace(asset_id="CAP-LOC-001", name="Control Room", category=AssetCategory.SHIP),
    )
    with pytest.raises(StoryBatchError, match="category"):
        service.discover("STORY-001")


def test_missing_cap_is_created_draft_only_after_review(review):
    service, caps, assets = review
    spec = SimpleNamespace(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Fixed engineering room",
        dependency_asset_ids=(),
        dependency_constraints=(),
    )
    caps.assets = assets
    assets.get.return_value = assets.list.return_value[0]
    item = SimpleNamespace(
        story_fingerprint="fingerprint",
        proposal=SimpleNamespace(specification=SimpleNamespace(category=AssetCategory.LOCATION)),
    )
    service.batch.current_story_fingerprint.return_value = item.story_fingerprint
    service.save_reviewed("STORY-001", spec, "fingerprint")
    service.batch.preview.assert_not_called()
    caps.create.assert_called_once()
    assert caps.create.call_args.args[0].status is CAPStatus.DRAFT
    service.batch.generator.save_reviewed.assert_called_once_with(spec)


def test_stale_story_fingerprint_never_creates_cap(review):
    service, caps, _ = review
    item = SimpleNamespace(
        story_fingerprint="changed",
        proposal=SimpleNamespace(specification=SimpleNamespace(category=AssetCategory.LOCATION)),
    )
    service.batch.current_story_fingerprint.return_value = item.story_fingerprint
    with pytest.raises(StoryBatchError, match="Story changed"):
        service.save_reviewed(
            "STORY-001",
            SimpleNamespace(asset_id="CAP-LOC-001", category=AssetCategory.LOCATION),
            "original",
        )
    caps.create.assert_not_called()
    service.batch.preview.assert_not_called()
