"""Isolated, in-memory spatial acceptance scenarios. No project records or AI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from vscs.application.caps.geometry_contract import CAPGeometry
from vscs.application.caps.spatial_graph import assess_spatial_graph
from vscs.application.caps.spatial_report import SpatialReviewReport, build_spatial_review_report
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import AssetCategory


class AcceptanceScenario(StrEnum):
    VALID = "valid"
    COLLISION = "collision"
    MISSING_GEOMETRY = "missing_geometry"


@dataclass(frozen=True)
class AcceptanceResult:
    scenario: AcceptanceScenario
    report: SpatialReviewReport


class _InMemorySpecifications:
    def __init__(self, items: dict[str, CAPStructuredSpecification]) -> None:
        self.items = items

    def get(self, asset_id: str) -> CAPStructuredSpecification | None:
        return self.items.get(asset_id)


def _geometry(size: tuple[int, int, int], origin: tuple[int, int, int]) -> CAPGeometry:
    return CAPGeometry.model_validate(
        {
            "frame_id": "acceptance-room",
            "size_mm": dict(zip(("x", "y", "z"), size, strict=True)),
            "origin_mm": dict(zip(("x", "y", "z"), origin, strict=True)),
        }
    )


def _specification(
    asset_id: str,
    category: AssetCategory,
    geometry: CAPGeometry | None,
    children: tuple[str, ...] = (),
) -> CAPStructuredSpecification:
    return CAPStructuredSpecification(
        asset_id=asset_id,
        category=category,
        design_intent="Synthetic acceptance geometry; not approved Story Canon",
        canonical_attributes={
            "architecture" if category is AssetCategory.LOCATION else "geometry": "Synthetic test"
        },
        master_prompt="Never send synthetic acceptance data to a generation provider.",
        geometry=geometry,
        dependency_asset_ids=children,
        dependency_constraints=tuple(
            DependencyConstraint(
                target_asset_id=child_id,
                relation=DependencyRelation.CONTAINS,
                minimum_clearance_mm=100,
                anchor="synthetic installation clearance",
            )
            for child_id in children
        ),
        origin="synthetic_acceptance_only",
    )


def run_spatial_acceptance(scenario: AcceptanceScenario) -> AcceptanceResult:
    """Evaluate a reproducible two-sibling fixture without touching disk or network."""
    child_ids = ("TEST-PRP-001", "TEST-PRP-002")
    parent = _specification(
        "TEST-LOC-001",
        AssetCategory.LOCATION,
        _geometry((8000, 5000, 2600), (0, 0, 0)),
        child_ids,
    )
    first = _specification(
        child_ids[0], AssetCategory.PROP, _geometry((1200, 600, 900), (800, 800, 100))
    )
    second_geometry = {
        AcceptanceScenario.VALID: _geometry((900, 700, 1000), (3400, 1200, 100)),
        AcceptanceScenario.COLLISION: _geometry((900, 700, 1000), (1400, 1000, 100)),
        AcceptanceScenario.MISSING_GEOMETRY: None,
    }[scenario]
    second = _specification(child_ids[1], AssetCategory.PROP, second_geometry)
    lookup = _InMemorySpecifications({child_ids[0]: first, child_ids[1]: second})
    return AcceptanceResult(
        scenario,
        build_spatial_review_report(assess_spatial_graph(parent, lookup)),
    )
