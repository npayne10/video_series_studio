"""Cross-asset design contracts: explicit, project-scoped and advisory."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.cross_asset_continuity import (
    DependencyConstraint,
    DependencyRelation,
    validate_dependencies,
)
from vscs.application.caps.service import CAPNotFoundError
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.domain.assets.models import AssetCategory


def _location(dependencies=("CAP-PRP-001",)):
    return CAPStructuredSpecification(
        asset_id="CAP-LOC-001",
        category=AssetCategory.LOCATION,
        design_intent="Vessel control room",
        canonical_attributes={"layout": "8 m long control room, console on forward wall"},
        master_prompt="Control room reference draft",
        dependency_asset_ids=dependencies,
    )


def _services():
    assets = Mock()
    assets.get.return_value = SimpleNamespace(category=AssetCategory.PROP)
    specs = Mock()
    specs.get.return_value = CAPStructuredSpecification(
        asset_id="CAP-PRP-001",
        category=AssetCategory.PROP,
        design_intent="Diagnostic console",
        canonical_attributes={"geometry": "Rectangular diagnostic console"},
        master_prompt="Console reference draft",
    )
    return assets, specs


def test_explicit_control_room_console_dependency_is_structurally_valid():
    assets, specs = _services()
    findings = validate_dependencies(
        _location(),
        (
            DependencyConstraint(
                target_asset_id="CAP-PRP-001", relation=DependencyRelation.CONTAINS
            ),
        ),
        assets,
        specs,
    )
    assert findings == ()
    assets.get.assert_called_once_with("CAP-PRP-001")


def test_missing_dependency_relation_is_flagged():
    assets, specs = _services()
    findings = validate_dependencies(_location(), (), assets, specs)
    assert [issue.code for issue in findings] == ["unresolved_dependency"]


def test_cross_project_unknown_asset_fails_closed():
    assets, specs = _services()
    assets.get.side_effect = KeyError("not registered")
    findings = validate_dependencies(
        _location(),
        (
            DependencyConstraint(
                target_asset_id="CAP-PRP-001", relation=DependencyRelation.CONTAINS
            ),
        ),
        assets,
        specs,
    )
    assert "missing_asset" in {issue.code for issue in findings}
    specs.get.assert_not_called()


def test_missing_target_spec_is_not_mistaken_for_verified_geometry():
    assets, specs = _services()
    specs.get.return_value = None
    findings = validate_dependencies(
        _location(),
        (
            DependencyConstraint(
                target_asset_id="CAP-PRP-001", relation=DependencyRelation.CONTAINS
            ),
        ),
        assets,
        specs,
    )
    assert "missing_target_spec" in {issue.code for issue in findings}



def test_registered_target_without_cap_is_advisory():
    assets, specs = _services()
    specs.get.side_effect = CAPNotFoundError("CAP not found for asset: CAP-PRP-001")
    findings = validate_dependencies(
        _location(),
        (
            DependencyConstraint(
                target_asset_id="CAP-PRP-001", relation=DependencyRelation.CONTAINS
            ),
        ),
        assets,
        specs,
    )
    assert [finding.code for finding in findings] == ["missing_target_spec"]


def test_clearance_requires_named_anchor_and_measured_geometry():
    with pytest.raises(ValueError, match="anchor"):
        DependencyConstraint(
            target_asset_id="CAP-PRP-001",
            relation=DependencyRelation.CONTAINS,
            minimum_clearance_mm=900,
        )
    assets, specs = _services()
    spec = _location().model_copy(
        update={"canonical_attributes": {"layout": "Compact control room"}}
    )
    findings = validate_dependencies(
        spec,
        (
            DependencyConstraint(
                target_asset_id="CAP-PRP-001",
                relation=DependencyRelation.CONTAINS,
                anchor="forward bulkhead",
                minimum_clearance_mm=900,
            ),
        ),
        assets,
        specs,
    )
    assert "unmeasured_geometry" in {issue.code for issue in findings}


def test_self_dependency_rejected():
    assets, specs = _services()
    findings = validate_dependencies(
        _location(("CAP-LOC-001",)),
        (
            DependencyConstraint(
                target_asset_id="CAP-LOC-001", relation=DependencyRelation.REFERENCES
            ),
        ),
        assets,
        specs,
    )
    assert "self_dependency" in {issue.code for issue in findings}
