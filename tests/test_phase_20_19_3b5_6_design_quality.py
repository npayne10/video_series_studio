"""Phase B.5.6: detect continuity risks without inventing or approving canon."""

from vscs.application.caps.design_quality import (
    assess_design_grounding,
    assess_design_quality,
)
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


def test_b525_shot_event_in_lighting_is_flagged():
    issues = assess_design_grounding(
        "The diagnostic console glows blue. The indicator pulses once in Shot 002.",
        (
            _field(
                "lighting",
                "Recessed fixtures; the small indicator pulses once then returns to steady glow.",
            ),
        ),
    )
    assert [issue.code for issue in issues] == ["transient_shot_event"]


def test_b525_unsupported_indicator_location_is_flagged():
    issues = assess_design_grounding(
        "An indicator is visible near the diagnostic console, but no placement is specified.",
        (_field("spatial_anchors", "A small indicator sits separately beside the doorway."),),
    )
    assert [issue.code for issue in issues] == ["unsupported_indicator_placement"]


def test_b525_explicit_story_spatial_support_is_respected():
    text = "A small indicator sits beside the doorway."
    assert not assess_design_grounding(
        text,
        (_field("spatial_anchors", "A small indicator sits beside the doorway."),),
    )


def test_b525_general_creative_design_is_not_mistaken_for_source_canon():
    assert not assess_design_grounding(
        "An engineering control room contains a console beside a workstation.",
        (
            _field("layout", "Proposed rectangular room with a centered doorway."),
            _field("scale", "Proposed 4.8 m by 3.6 m interior, not an established Story fact."),
            _field("lighting", "Proposed neutral-white recessed lighting fixtures."),
            _field("spatial_anchors", "Keep the indicator's mounting unspecified."),
        ),
    )
