"""Unit coverage for Phase 18.2.11.2.6 category reference templates."""

import pytest
from pydantic import ValidationError

from vscs.domain.assets import AssetCategory
from vscs.domain.caps import (
    CanonicalReferenceView,
    CategoryReferenceTemplate,
    ReferenceRequirement,
    default_category_reference_templates,
)


def test_default_registry_covers_every_asset_category() -> None:
    registry = default_category_reference_templates()

    assert set(registry.categories()) == set(AssetCategory)
    for category in AssetCategory:
        template = registry.require(category)
        assert template.category is category
        assert CanonicalReferenceView.MASTER in template.required_views


def test_ship_template_requires_complete_exterior_turnaround() -> None:
    template = default_category_reference_templates().require(AssetCategory.SHIP)

    assert set(template.required_views) == {
        CanonicalReferenceView.MASTER,
        CanonicalReferenceView.FRONT,
        CanonicalReferenceView.REAR,
        CanonicalReferenceView.PORT,
        CanonicalReferenceView.STARBOARD,
        CanonicalReferenceView.TOP,
        CanonicalReferenceView.BOTTOM,
    }
    assert template.requirement_for(CanonicalReferenceView.TOP) is ReferenceRequirement.REQUIRED
    assert (
        template.requirement_for(CanonicalReferenceView.PRIMARY_THREE_QUARTER)
        is ReferenceRequirement.RECOMMENDED
    )
    assert (
        template.requirement_for(CanonicalReferenceView.INTERIOR) is ReferenceRequirement.OPTIONAL
    )


def test_character_template_focuses_on_identity_coverage() -> None:
    template = default_category_reference_templates().require(AssetCategory.CHARACTER)

    assert CanonicalReferenceView.FULL_BODY in template.required_views
    assert CanonicalReferenceView.FACE in template.required_views
    assert CanonicalReferenceView.PROFILE_LEFT in template.required_views
    assert CanonicalReferenceView.PROFILE_RIGHT in template.required_views
    assert CanonicalReferenceView.FRONT in template.recommended_views


def test_template_rejects_overlapping_requirement_sets() -> None:
    with pytest.raises(ValidationError, match="must be disjoint"):
        CategoryReferenceTemplate(
            category=AssetCategory.SHIP,
            required_views=(CanonicalReferenceView.MASTER, CanonicalReferenceView.TOP),
            recommended_views=(CanonicalReferenceView.TOP,),
        )


def test_template_registry_can_replace_default_for_future_project_override() -> None:
    registry = default_category_reference_templates()
    override = CategoryReferenceTemplate(
        category=AssetCategory.OTHER,
        required_views=(CanonicalReferenceView.MASTER, CanonicalReferenceView.FRONT),
    )

    registry.register(override)

    assert registry.require(AssetCategory.OTHER) == override
