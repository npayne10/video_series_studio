"""B.5.22: real SQLite-backed reviewed Draft CAP acceptance in disposable storage.

No existing operator project, paid provider, Canon approval, or media is touched.
"""

import json
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from vscs.application.assets.repository import AssetRepository
from vscs.application.assets.service import AssetService
from vscs.application.caps.design_completion import (
    DESIGN_REVIEW_KEY,
    DesignFieldReview,
    DesignReviewPackage,
    DesignReviewPersistence,
    DetailDecision,
    DetailOrigin,
)
from vscs.application.caps.governed_planning_evidence import ProductionPlanningContracts
from vscs.application.caps.repository import CAPRepository
from vscs.application.caps.service import CAPNotFoundError, CAPService
from vscs.application.caps.story_batch import StoryBatchError, StoryCAPBatchService
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
    CAPStructuredSpecificationService,
)
from vscs.application.story.asset_resolver import (
    AssetBindingStatus,
    ShotAssetBinding,
)
from vscs.application.story.episode_planning import EpisodePlan, EpisodePlanStatus
from vscs.application.story.lifecycle import StoryLifecycleService, StoryStatus
from vscs.application.story.scene_planning import ScenePlan, ScenePlanStatus
from vscs.application.story.shot_planning import ShotPlan, ShotPlanStatus
from vscs.domain.assets.models import AssetCategory, AssetCreate, AssetStatus
from vscs.domain.caps import CAPStatus
from vscs.domain.projects import ProjectMetadata
from vscs.infrastructure.database import DatabaseManager

STORY_ID = "STORY-001"
ASSET_ID = "CAP-LOC-001"


def _write_plan(root, name, key, value):
    destination = root / "planning" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps({key: [asdict(value)]}), encoding="utf-8")


def _create_planning(root):
    calculator = ProductionPlanningContracts()
    episode = EpisodePlan(
        episode_id="EP-001",
        story_id=STORY_ID,
        sequence_number=1,
        title="A disposable episode",
        story_scope="An empty engineering control room",
        production_objective="Observe the console",
        target_runtime_seconds=15,
        status=EpisodePlanStatus.READY,
    )
    scene = ScenePlan(
        scene_id="EP-001-SCN-001",
        episode_id=episode.episode_id,
        sequence_number=1,
        title="Quiet room",
        story_scope="A stationary diagnostic console",
        production_objective="Watch the console",
        target_runtime_seconds=15,
        setting_requirement="Engineering room",
        required_events=("Console stays on",),
        episode_contract_hash=calculator.episode_contract_hash(asdict(episode)),
        status=ScenePlanStatus.READY,
    )
    shot = ShotPlan(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id=scene.scene_id,
        sequence_number=1,
        title="Fixed watch",
        narrative_purpose="Observe the steady diagnostic console",
        production_objective="Keep the camera fixed",
        target_runtime_seconds=15,
        required_action="In the engineering room, the console stays steady.",
        scene_contract_hash=calculator.scene_contract_hash(asdict(scene)),
        status=ShotPlanStatus.READY,
    )
    binding = ShotAssetBinding(
        binding_id="EP-001-SCN-001-SHT-001-AST-001",
        shot_id=shot.shot_id,
        sequence_number=1,
        role="location",
        requirement="Engineering room",
        expected_category=AssetCategory.LOCATION,
        asset_id=ASSET_ID,
        shot_contract_hash=calculator.shot_contract_hash(asdict(shot)),
        status=AssetBindingStatus.DRAFT,
    )
    for name, key, record in (
        ("episode_plans.json", "episodes", episode),
        ("scene_plans.json", "scenes", scene),
        ("shot_plans.json", "shots", shot),
        ("asset_resolutions.json", "bindings", binding),
    ):
        _write_plan(root, name, key, record)


def _services(root, database):
    projects = SimpleNamespace(project_directory=root, is_project_open=True)
    assets = AssetService(projects, AssetRepository(database))
    caps = CAPService(assets, CAPRepository(database))
    specifications = CAPStructuredSpecificationService(caps)
    stories = StoryLifecycleService(projects)
    generator = SimpleNamespace(
        generator=SimpleNamespace(assets=assets),
        specifications=specifications,
    )
    batch = StoryCAPBatchService(stories, generator)
    return assets, caps, specifications, stories, StoryCAPBatchReviewService(batch)


@pytest.fixture
def disposable_disk_project(tmp_path):
    root = tmp_path / "B5_22_DISPOSABLE_CAP_ACCEPTANCE"
    root.mkdir()
    metadata = ProjectMetadata(name="Disposable CAP acceptance")
    database = DatabaseManager()
    database.open(root, metadata)
    assets, caps, specifications, stories, review = _services(root, database)
    assets.create(
        AssetCreate(
            asset_id=ASSET_ID,
            name="Engineering control room",
            category=AssetCategory.LOCATION,
            status=AssetStatus.DRAFT,
        )
    )
    story = stories.create_story(
        title="Disposable Quiet Console",
        description="A quiet engineering room contains a diagnostic console.",
    )
    assert story.story_id == STORY_ID
    stories.set_status(STORY_ID, StoryStatus.APPROVED)
    _create_planning(root)
    yield root, metadata, database, assets, caps, specifications, review
    database.close()


def _draft_specification():
    return CAPStructuredSpecification(
        asset_id=ASSET_ID,
        category=AssetCategory.LOCATION,
        design_intent="A fixed engineering interior",
        canonical_attributes={"architecture": "A stationary control room"},
        master_prompt="Proposed room design; not approved.",
        origin="operator_reviewed_proposal",
    )


def _explicit_review(specification, story_fingerprint, context_fingerprint):
    return DesignReviewPackage(
        asset_id=ASSET_ID,
        base_fingerprint=specification.fingerprint(),
        reviewer="B5.22 Test Operator",
        story_fingerprint=story_fingerprint,
        context_fingerprint=context_fingerprint,
        fields=(
            DesignFieldReview(
                field="architecture",
                proposed_value="A stationary control room",
                final_value="A stationary control room",
                decision=DetailDecision.EDIT,
                origin=DetailOrigin.DESIGN_PROPOSAL,
                rationale="Reviewed design, not proven Canon.",
            ),
            *(
                DesignFieldReview(
                    field=field,
                    decision=DetailDecision.DEFER,
                    origin=DetailOrigin.UNRESOLVED,
                )
                for field in ("layout", "scale", "materials", "spatial_anchors", "lighting")
            ),
        ),
    )


def _save(review):
    specification = _draft_specification()
    story_fingerprint = review.batch.current_story_fingerprint(STORY_ID)
    context = review.prepare_context(STORY_ID, ASSET_ID)
    review.save_reviewed(
        STORY_ID,
        specification,
        story_fingerprint,
        _explicit_review(specification, story_fingerprint, context.fingerprint),
        expected_context_fingerprint=context.fingerprint,
    )


def test_disk_backed_draft_survives_database_close_and_reopen(disposable_disk_project):
    root, metadata, database, assets, caps, specifications, review = disposable_disk_project
    _save(review)
    assert len(caps.list()) == 1
    original = caps.get(ASSET_ID)
    assert original.status is CAPStatus.DRAFT
    assert original.reference_paths == ()
    assert assets.get(ASSET_ID).status is AssetStatus.DRAFT
    assert SPECIFICATION_METADATA_KEY in original.production_metadata
    audit = json.loads(original.production_metadata[DESIGN_REVIEW_KEY])
    assert audit["canon_approved"] is False
    assert audit["image_authorized"] is False
    assert audit["story_fingerprint"] == review.batch.current_story_fingerprint(STORY_ID)
    assert audit["context_fingerprint"] == review.prepare_context(STORY_ID, ASSET_ID).fingerprint
    assert len(audit["fields"]) == 6
    assert specifications.get(ASSET_ID) is not None

    database.close()
    reopened = DatabaseManager()
    reopened.open(root, metadata)
    try:
        reloaded_assets, reloaded_caps, reloaded_specs, _, _ = _services(root, reopened)
        persisted = reloaded_caps.get(ASSET_ID)
        assert persisted.status is CAPStatus.DRAFT
        assert persisted.reference_paths == ()
        assert persisted.production_metadata == original.production_metadata
        assert reloaded_specs.get(ASSET_ID) is not None
        assert reloaded_assets.get(ASSET_ID).status is AssetStatus.DRAFT
        assert reopened.check_integrity()
    finally:
        reopened.close()


def test_disk_backed_failure_removes_new_empty_draft(disposable_disk_project):
    _root, _metadata, _database, _assets, caps, _specifications, review = (
        disposable_disk_project
    )
    with patch.object(
        DesignReviewPersistence, "save", side_effect=RuntimeError("Injected save failure")
    ):
        with pytest.raises(RuntimeError, match="Injected save failure"):
            _save(review)
    assert caps.list() == ()
    with pytest.raises(CAPNotFoundError):
        caps.get(ASSET_ID)


def test_disk_backed_stale_context_does_not_create_cap(disposable_disk_project):
    root, _metadata, _database, _assets, caps, _specifications, review = (
        disposable_disk_project
    )
    context = review.prepare_context(STORY_ID, ASSET_ID)
    story_fingerprint = review.batch.current_story_fingerprint(STORY_ID)
    specification = _draft_specification()
    shot_path = root / "planning" / "shot_plans.json"
    payload = json.loads(shot_path.read_text(encoding="utf-8"))
    payload["shots"][0]["required_action"] = "An unapproved revised scene"
    shot_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(StoryBatchError, match="context changed"):
        review.save_reviewed(
            STORY_ID,
            specification,
            story_fingerprint,
            _explicit_review(specification, story_fingerprint, context.fingerprint),
            expected_context_fingerprint=context.fingerprint,
        )
    assert caps.list() == ()


def test_disk_update_failure_rolls_back_new_cap(disposable_disk_project):
    _root, _metadata, _database, _assets, caps, _specifications, review = (
        disposable_disk_project
    )
    with patch.object(CAPRepository, "update", side_effect=RuntimeError("Disk update failed")):
        with pytest.raises(RuntimeError, match="Disk update failed"):
            _save(review)
    assert caps.list() == ()


def test_disk_repeated_save_does_not_overwrite_first_review(disposable_disk_project):
    _root, _metadata, _database, _assets, caps, _specifications, review = (
        disposable_disk_project
    )
    _save(review)
    before = caps.get(ASSET_ID).production_metadata
    with pytest.raises(StoryBatchError, match="existing|already exists|revision"):
        _save(review)
    assert len(caps.list()) == 1
    assert caps.get(ASSET_ID).production_metadata == before
