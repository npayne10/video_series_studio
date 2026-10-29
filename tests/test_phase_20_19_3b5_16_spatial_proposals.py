"""B.5.16 offline proposals require explicit stored relationship evidence."""

from vscs.application.caps.spatial_proposals import propose_spatial_relationships
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory


def _spec(asset_id, category, links=()):
    return CAPStructuredSpecification(
        asset_id=asset_id,
        category=category,
        design_intent="Evidence only, no inferred measurement",
        canonical_attributes={
            "architecture" if category is AssetCategory.LOCATION else "geometry": "Unknown"
        },
        master_prompt="Unapproved Draft",
        dependency_asset_ids=tuple(item.target_asset_id for item in links),
        dependency_constraints=links,
    )


def test_explicit_reverse_location_proposes_parent_containment():
    parent = _spec("CAP-LOC-001", AssetCategory.LOCATION)
    child = _spec(
        "CAP-PRP-001",
        AssetCategory.PROP,
        (
            DependencyConstraint(
                target_asset_id="CAP-LOC-001", relation=DependencyRelation.LOCATED_IN
            ),
        ),
    )
    plan = propose_spatial_relationships(parent, (child,))
    assert len(plan.proposed) == 1
    assert plan.proposed[0].relation is DependencyRelation.CONTAINS
    assert "located_in" in plan.proposed[0].evidence
    assert any("placement/clearance not inferred" in gap for gap in plan.unresolved)


def test_no_reverse_link_never_invents_relationship():
    parent = _spec("CAP-LOC-001", AssetCategory.LOCATION)
    child = _spec("CAP-PRP-001", AssetCategory.PROP)
    plan = propose_spatial_relationships(parent, (child,))
    assert plan.proposed == ()
    assert any("Parent geometry missing" in gap for gap in plan.unresolved)


def test_existing_containment_is_not_reproposed():
    link = DependencyConstraint(target_asset_id="CAP-PRP-001", relation=DependencyRelation.CONTAINS)
    parent = _spec("CAP-LOC-001", AssetCategory.LOCATION, (link,))
    child = _spec(
        "CAP-PRP-001",
        AssetCategory.PROP,
        (
            DependencyConstraint(
                target_asset_id="CAP-LOC-001", relation=DependencyRelation.LOCATED_IN
            ),
        ),
    )
    assert propose_spatial_relationships(parent, (child,)).proposed == ()
