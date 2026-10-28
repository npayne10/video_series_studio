"""Read-only validation of explicit CAP-to-CAP dependency and spatial constraints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from vscs.application.caps.anchor_placement import place_at_anchor
from vscs.application.caps.geometry_contract import check_containment
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.structured_specification import (
    CAPStructuredSpecification,
    DependencyConstraint,
    DependencyRelation,
)
from vscs.domain.assets.models import Asset, AssetCategory


@dataclass(frozen=True)
class ContinuityFinding:
    code: str
    message: str
    asset_id: str
    target_asset_id: str = ""


class AssetLookup(Protocol):
    def get(self, asset_id: str) -> Asset: ...


class SpecificationLookup(Protocol):
    def get(self, asset_id: str) -> CAPStructuredSpecification | None: ...


_MEASURED = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mm|cm|m|metres?|meters?)\b", re.I)


def validate_dependencies(
    specification: CAPStructuredSpecification,
    constraints: tuple[DependencyConstraint, ...],
    assets: AssetLookup,
    specifications: SpecificationLookup,
) -> tuple[ContinuityFinding, ...]:
    """Fail closed for missing identities and incompatible declared relations.

    Missing target specifications are advisory, never invented. This validator cannot
    prove geometric non-intersection from prose; physical verification remains pending.
    """
    findings: list[ContinuityFinding] = []
    expected = set(specification.dependency_asset_ids)
    claimed = {constraint.target_asset_id.upper() for constraint in constraints}
    if len(claimed) != len(constraints):
        findings.append(
            ContinuityFinding(
                "duplicate_relation", "Duplicate target relationship", specification.asset_id
            )
        )
    for missing in sorted(expected - claimed):
        findings.append(
            ContinuityFinding(
                "unresolved_dependency",
                "Declared dependency has no reviewed relationship constraint",
                specification.asset_id,
                missing,
            )
        )
    for constraint in constraints:
        target_id = constraint.target_asset_id.upper()
        if target_id == specification.asset_id:
            findings.append(
                ContinuityFinding(
                    "self_dependency",
                    "Asset cannot depend on itself",
                    specification.asset_id,
                    target_id,
                )
            )
            continue
        if target_id not in expected:
            findings.append(
                ContinuityFinding(
                    "undeclared_dependency",
                    "Relationship target is absent from the specification dependency IDs",
                    specification.asset_id,
                    target_id,
                )
            )
        try:
            target = assets.get(target_id)
        except (KeyError, LookupError, ValueError):
            findings.append(
                ContinuityFinding(
                    "missing_asset",
                    "Target asset is not registered in this project",
                    specification.asset_id,
                    target_id,
                )
            )
            continue
        if constraint.relation in {
            DependencyRelation.CONTAINS,
            DependencyRelation.MOUNTED_IN,
        } and specification.category not in {
            AssetCategory.LOCATION,
            AssetCategory.SHIP,
            AssetCategory.VEHICLE,
        }:
            findings.append(
                ContinuityFinding(
                    "invalid_container",
                    "Asset category cannot contain another physical asset",
                    specification.asset_id,
                    target_id,
                )
            )
        if constraint.relation is DependencyRelation.LOCATED_IN and target.category not in {
            AssetCategory.LOCATION,
            AssetCategory.SHIP,
            AssetCategory.VEHICLE,
        }:
            findings.append(
                ContinuityFinding(
                    "invalid_location",
                    "Located-in target must be a location, ship or vehicle",
                    specification.asset_id,
                    target_id,
                )
            )
        try:
            target_spec = specifications.get(target_id)
        except (CAPNotFoundError, KeyError, LookupError, ValueError):
            target_spec = None
        if target_spec is None:
            findings.append(
                ContinuityFinding(
                    "missing_target_spec",
                    "Target CAP specification is not yet available for physical verification",
                    specification.asset_id,
                    target_id,
                )
            )
        elif target_spec.category != target.category:
            findings.append(
                ContinuityFinding(
                    "target_category_mismatch",
                    "Target CAP category differs from registered asset",
                    specification.asset_id,
                    target_id,
                )
            )
        elif constraint.relation is DependencyRelation.CONTAINS:
            if specification.geometry is None or target_spec.geometry is None:
                findings.append(
                    ContinuityFinding(
                        "missing_typed_geometry",
                        "Typed bounds for both assets are required for physical verification",
                        specification.asset_id,
                        target_id,
                    )
                )
            else:
                resolved = target_spec.geometry
                if constraint.placement is not None:
                    resolved, placement_issues = place_at_anchor(
                        specification.geometry, resolved, constraint.placement
                    )
                    for issue in placement_issues:
                        findings.append(
                            ContinuityFinding(
                                issue.code, issue.message, specification.asset_id, target_id
                            )
                        )
                if resolved is not None:
                    for issue in check_containment(
                        specification.geometry, resolved, constraint.minimum_clearance_mm
                    ):
                        findings.append(
                            ContinuityFinding(
                                issue.code, issue.message, specification.asset_id, target_id
                            )
                        )
        if (
            constraint.minimum_clearance_mm is not None
            and specification.geometry is None
            and not _MEASURED.search(" ".join(specification.canonical_attributes.values()))
        ):
            findings.append(
                ContinuityFinding(
                    "unmeasured_geometry",
                    "Clearance is declared but source geometry has no measurable dimensions",
                    specification.asset_id,
                    target_id,
                )
            )
    return tuple(findings)
