"""Shot spatial extraction uses only authorized text and explicit bound identities."""

from vscs.application.caps.shot_spatial_evidence import (
    ShotSpatialSource,
    inspect_shot_spatial_evidence,
)
from vscs.domain.assets.models import Asset


def _assets():
    return (
        Asset.model_construct(asset_id="CAP-PRP-001", name="Diagnostic Console"),
        Asset.model_construct(asset_id="CAP-LOC-001", name="Engineering Control Room"),
    )


def test_shot_relation_provenance_from_explicit_text_and_bindings():
    source = ShotSpatialSource(
        "SHT-001",
        "STORY-001",
        "Diagnostic Console is located in Engineering Control Room.",
        ("CAP-LOC-001", "CAP-PRP-001"),
    )
    report = inspect_shot_spatial_evidence((source,), _assets(), "STORY-001")
    assert len(report.findings) == 1
    assert report.findings[0].shot_id == "SHT-001"
    assert report.findings[0].child_asset_id == "CAP-PRP-001"
    assert report.findings[0].excerpt in source.text


def test_binding_alone_is_not_relationship_evidence():
    source = ShotSpatialSource(
        "SHT-001", "STORY-001", "", ("CAP-LOC-001", "CAP-PRP-001")
    )
    report = inspect_shot_spatial_evidence((source,), _assets(), "STORY-001")
    assert report.findings == ()
    assert report.unresolved == ("SHT-001: Shot text unavailable; bindings are not prose",)


def test_unbound_or_other_story_relationships_are_rejected():
    unbound = ShotSpatialSource(
        "SHT-001",
        "STORY-001",
        "Diagnostic Console inside Engineering Control Room.",
        ("CAP-LOC-001",),
    )
    other_story = ShotSpatialSource(
        "SHT-002",
        "STORY-002",
        "Diagnostic Console inside Engineering Control Room.",
        ("CAP-LOC-001", "CAP-PRP-001"),
    )
    result = inspect_shot_spatial_evidence(
        (unbound, other_story), _assets(), "STORY-001"
    )
    assert not result.findings
