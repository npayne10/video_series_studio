"""Read-only multi-asset spatial continuity assessment in one parent coordinate frame."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from vscs.application.caps.anchor_placement import check_collision, place_at_anchor
from vscs.application.caps.geometry_contract import CAPGeometry, check_containment
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyRelation,
)


class SpatialSpecificationLookup(Protocol):
    def get(self, asset_id: str) -> CAPStructuredSpecification | None: ...


@dataclass(frozen=True)
class SpatialGraphFinding:
    code: str
    message: str
    asset_ids: tuple[str, ...]


@dataclass(frozen=True)
class SpatialGraphReport:
    parent_asset_id: str
    placed_asset_ids: tuple[str, ...]
    findings: tuple[SpatialGraphFinding, ...]
    verified: bool


def assess_spatial_graph(
    parent: CAPStructuredSpecification,
    specifications: SpatialSpecificationLookup,
) -> SpatialGraphReport:
    """Resolve declared contained siblings; never infer absent physical assets.

    No writes, provider calls, rotations, or canonical authority changes.
    """
    findings: list[SpatialGraphFinding] = []
    placed: dict[str, CAPGeometry] = {}
    if parent.geometry is None:
        return SpatialGraphReport(
            parent.asset_id,
            (),
            (
                SpatialGraphFinding(
                    "missing_parent_geometry",
                    "Parent needs typed geometry before scene continuity can be checked",
                    (parent.asset_id,),
                ),
            ),
            False,
        )
    children = tuple(
        item
        for item in parent.dependency_constraints
        if item.relation is DependencyRelation.CONTAINS
    )
    declared = {item.target_asset_id for item in children}
    for child_id in sorted(set(parent.dependency_asset_ids) - declared):
        findings.append(
            SpatialGraphFinding(
                "unresolved_dependency",
                "Dependency is not declared as a contained sibling",
                (parent.asset_id, child_id),
            )
        )
    for constraint in children:
        target_id = constraint.target_asset_id
        try:
            target_spec = specifications.get(target_id)
        except CAPNotFoundError:
            target_spec = None
        if target_spec is None or target_spec.geometry is None:
            findings.append(
                SpatialGraphFinding(
                    "missing_child_geometry",
                    "Target CAP or its typed geometry is unavailable",
                    (parent.asset_id, target_id),
                )
            )
            continue
        child_geometry = target_spec.geometry
        if constraint.placement is not None:
            placed_geometry, placement_findings = place_at_anchor(
                parent.geometry, child_geometry, constraint.placement
            )
            for placement_issue in placement_findings:
                findings.append(
                    SpatialGraphFinding(
                        placement_issue.code, placement_issue.message, (parent.asset_id, target_id)
                    )
                )
            if placed_geometry is None:
                continue
            child_geometry = placed_geometry
        containment = check_containment(
            parent.geometry, child_geometry, constraint.minimum_clearance_mm
        )
        if containment:
            for containment_issue in containment:
                findings.append(
                    SpatialGraphFinding(
                        containment_issue.code,
                        containment_issue.message,
                        (parent.asset_id, target_id),
                    )
                )
            continue
        placed[target_id] = child_geometry
    ids = tuple(sorted(placed))
    for index, first_id in enumerate(ids):
        for second_id in ids[index + 1 :]:
            for issue in check_collision(placed[first_id], placed[second_id]):
                findings.append(
                    SpatialGraphFinding(issue.code, issue.message, (first_id, second_id))
                )
    return SpatialGraphReport(parent.asset_id, ids, tuple(findings), not findings)
