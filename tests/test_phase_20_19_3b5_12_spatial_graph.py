"""Sibling collision and missing-data continuity are local and deterministic."""

from unittest.mock import Mock

from vscs.application.caps.geometry_contract import CAPGeometry
from vscs.application.caps.spatial_graph import assess_spatial_graph
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory


def _geo(size: int, origin: int = 0) -> CAPGeometry:
    return CAPGeometry.model_validate(
        {
            "frame_id": "room",
            "origin_mm": {"x": origin, "y": 0, "z": 0},
            "size_mm": {"x": size, "y": size, "z": size},
        }
    )


def _spec(asset_id: str, geometry: CAPGeometry | None, *, children: tuple[str, ...] = ()):
    return CAPStructuredSpecification(
        asset_id=asset_id,
        category=AssetCategory.LOCATION if children else AssetCategory.PROP,
        design_intent="Draft",
        canonical_attributes={"layout" if children else "geometry": "Draft"},
        master_prompt="Draft",
        geometry=geometry,
        dependency_asset_ids=children,
        dependency_constraints=tuple(
            DependencyConstraint(target_asset_id=child, relation=DependencyRelation.CONTAINS)
            for child in children
        ),
    )


def test_multiple_non_overlapping_siblings_are_reported_as_compatible():
    parent = _spec("CAP-LOC-001", _geo(2000), children=("CAP-PRP-001", "CAP-PRP-002"))
    specs = Mock()
    specs.get.side_effect = {
        "CAP-PRP-001": _spec("CAP-PRP-001", _geo(200, 100)),
        "CAP-PRP-002": _spec("CAP-PRP-002", _geo(200, 700)),
    }.get
    result = assess_spatial_graph(parent, specs)
    assert result.verified
    assert result.placed_asset_ids == ("CAP-PRP-001", "CAP-PRP-002")
    specs.get.assert_any_call("CAP-PRP-001")


def test_overlapping_siblings_flag_collision_with_asset_pair():
    parent = _spec("CAP-LOC-001", _geo(2000), children=("CAP-PRP-001", "CAP-PRP-002"))
    specs = Mock()
    specs.get.side_effect = {
        "CAP-PRP-001": _spec("CAP-PRP-001", _geo(300, 100)),
        "CAP-PRP-002": _spec("CAP-PRP-002", _geo(300, 200)),
    }.get
    result = assess_spatial_graph(parent, specs)
    assert not result.verified
    assert [(item.code, item.asset_ids) for item in result.findings] == [
        ("collision", ("CAP-PRP-001", "CAP-PRP-002"))
    ]


def test_missing_sibling_geometry_never_passes_verification():
    parent = _spec("CAP-LOC-001", _geo(2000), children=("CAP-PRP-001",))
    specs = Mock()
    specs.get.return_value = None
    report = assess_spatial_graph(parent, specs)
    assert not report.verified
    assert report.findings[0].code == "missing_child_geometry"
