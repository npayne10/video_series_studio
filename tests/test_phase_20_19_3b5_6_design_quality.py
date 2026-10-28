"""Phase B.5.6: detect continuity risks without inventing or approving canon."""

from vscs.application.caps.design_quality import assess_design_quality
from vscs.application.caps.provider_design_expansion import ProposedDesignField
from vscs.domain.assets.models import AssetCategory


def _field(name: str, value: str) -> ProposedDesignField:
    return ProposedDesignField(field=name, proposed_value=value, rationale="Design only")


def test_camera_relative_layout_flags_continuity_risk():
    issues = assess_design_quality(
        AssetCategory.LOCATION,
        (_field("layout", "Console in foreground, workstation in background."),),
    )
    assert "camera_dependent" in {issue.code for issue in issues}


def test_qualitative_scale_needs_measured_dimensions():
    issues = assess_design_quality(
        AssetCategory.LOCATION,
        (_field("scale", "Human-scaled and moderately confined."),),
    )
    assert "unmeasured_scale" in {issue.code for issue in issues}


def test_measured_scale_and_stable_console_anchor_are_not_flagged():
    issues = assess_design_quality(
        AssetCategory.LOCATION,
        (
            _field("scale", "Room 8 m long by 5 m wide, provisional design."),
            _field("layout", "Console fixed to forward bulkhead; workstation to starboard wall."),
        ),
    )
    assert not issues


def test_missing_console_or_workstation_triggers_anchor_check():
    issues = assess_design_quality(
        AssetCategory.LOCATION,
        (_field("layout", "Open empty chamber with access hatch."),),
    )
    assert "missing_functional_anchor" in {issue.code for issue in issues}


def test_unrelated_prop_is_not_subject_to_location_anchor_rule():
    issues = assess_design_quality(
        AssetCategory.PROP, (_field("geometry", "Rectangular housing with front panel."),)
    )
    assert not issues
