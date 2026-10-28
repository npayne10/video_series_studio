"""Phase 20.19.3B.5.1 asset discovery and missing Draft CAP review gates."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.story_batch import StoryBatchError
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus


@pytest.fixture
def review(tmp_path: Path):
    planning = tmp_path / "planning"
    planning.mkdir()
    (planning / "asset_resolutions.json").write_text(
        json.dumps(
            {
                "bindings": [
                    {"asset_id": "CAP-LOC-001", "expected_category": "location"},
                    {"asset_id": "CAP-LOC-001", "expected_category": "location"},
                    {"asset_id": "CAP-PRP-001", "expected_category": "prop"},
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
    batch.generator.generator.assets = assets
    batch.generator.specifications.caps = caps
    batch.generator.specifications.get.return_value = None
    return StoryCAPBatchReviewService(batch), caps, assets


def test_discovery_deduplicates_registered_bound_assets(review):
    service, _, _ = review
    discovered = service.discover()
    assert [x.asset_id for x in discovered] == ["CAP-LOC-001", "CAP-PRP-001"]
    assert all(not x.has_cap for x in discovered)


def test_discovery_rejects_category_collision(review):
    service, _, assets = review
    assets.list.return_value = (
        SimpleNamespace(asset_id="CAP-LOC-001", name="Control Room", category=AssetCategory.SHIP),
    )
    with pytest.raises(StoryBatchError, match="category"):
        service.discover()


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
