"""Typed geometry checks propagate into reviewed CAP dependency decisions."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.geometry_contract import CAPGeometry
from vscs.application.caps.story_batch import StoryBatchError
from vscs.application.caps.story_batch_review import StoryCAPBatchReviewService
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory


def _geometry(size: int, origin: int = 0) -> CAPGeometry:
    return CAPGeometry.model_validate(
        {
            "frame_id": "room",
            "size_mm": {"x": size, "y": size, "z": size},
            "origin_mm": {"x": origin, "y": origin, "z": origin},
        }
    )


def _spec(asset_id: str, category: AssetCategory, geometry: CAPGeometry):
    dependencies = ("CAP-PRP-001",) if category is AssetCategory.LOCATION else ()
    constraints = (
        (
            DependencyConstraint(
                target_asset_id="CAP-PRP-001",
                relation=DependencyRelation.CONTAINS,
                anchor="mount",
                minimum_clearance_mm=100,
            ),
        )
        if dependencies
        else ()
    )
    return CAPStructuredSpecification(
        asset_id=asset_id,
        category=category,
        design_intent="Design",
        canonical_attributes={"layout" if dependencies else "geometry": "Draft"},
        master_prompt="Draft",
        dependency_asset_ids=dependencies,
        dependency_constraints=constraints,
        geometry=geometry,
    )


def test_contained_geometry_passes_draft_preflight_without_provider():
    batch = Mock()
    caps = batch.generator.specifications.caps
    caps.assets.get.return_value = SimpleNamespace(category=AssetCategory.PROP)
    batch.generator.specifications.get.return_value = _spec(
        "CAP-PRP-001", AssetCategory.PROP, _geometry(100, 300)
    )
    review = StoryCAPBatchReviewService(batch)
    assert review.validate_reviewed_dependencies(
        _spec("CAP-LOC-001", AssetCategory.LOCATION, _geometry(1000))
    ) == ()
    batch.generator.propose.assert_not_called()
    caps.create.assert_not_called()


def test_out_of_bounds_geometry_blocks_draft_preflight():
    batch = Mock()
    batch.generator.specifications.caps.assets.get.return_value = SimpleNamespace(
        category=AssetCategory.PROP
    )
    batch.generator.specifications.get.return_value = _spec(
        "CAP-PRP-001", AssetCategory.PROP, _geometry(500, 900)
    )
    review = StoryCAPBatchReviewService(batch)
    with pytest.raises(StoryBatchError, match="clearance"):
        review.validate_reviewed_dependencies(
            _spec("CAP-LOC-001", AssetCategory.LOCATION, _geometry(1000))
        )
    batch.generator.specifications.caps.create.assert_not_called()
