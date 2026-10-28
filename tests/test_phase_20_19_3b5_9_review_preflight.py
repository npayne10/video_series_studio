"""Review-time dependency validation must not create CAPs or invoke OpenAI."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.story_batch import StoryBatchError
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory


def _spec(target: str) -> CAPStructuredSpecification:
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Engineering control room",
        canonical_attributes={"layout": "Compact vessel control room"},
        master_prompt="Draft reference",
        dependency_asset_ids=(target,),
        dependency_constraints=(
            DependencyConstraint(
                target_asset_id=target,
                relation=DependencyRelation.CONTAINS,
                anchor="forward bulkhead",
                minimum_clearance_mm=900,
            ),
        ),
    )


def _review_service() -> tuple[StoryCAPBatchReviewService, Mock]:
    batch = Mock()
    caps = batch.generator.specifications.caps
    caps.assets.get.return_value = SimpleNamespace(category=AssetCategory.PROP)
    batch.generator.specifications.get.return_value = None
    return StoryCAPBatchReviewService(batch), caps


def test_registered_console_is_flagged_unverified_but_not_approved():
    review, caps = _review_service()
    warnings = review.validate_reviewed_dependencies(_spec("CAP-PRP-001"))
    assert any("physical verification" in warning for warning in warnings)
    assert any("measurable dimensions" in warning for warning in warnings)
    caps.create.assert_not_called()
    review.batch.generator.propose.assert_not_called()


def test_unknown_project_asset_is_blocked_without_persistence():
    review, caps = _review_service()
    caps.assets.get.side_effect = KeyError("not registered")
    with pytest.raises(StoryBatchError, match="not registered"):
        review.validate_reviewed_dependencies(_spec("CAP-PRP-999"))
    caps.create.assert_not_called()
    review.batch.generator.propose.assert_not_called()


def test_no_dependencies_need_no_lookups():
    review, caps = _review_service()
    specification = _spec("CAP-PRP-001").model_copy(
        update={"dependency_asset_ids": (), "dependency_constraints": ()}
    )
    assert review.validate_reviewed_dependencies(specification) == ()
    caps.assets.get.assert_not_called()
