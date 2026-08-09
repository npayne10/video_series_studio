"""Domain contract tests for Production Projection API."""

from vscs.domain.assets import AssetCategory
from vscs.domain.caps import (
    CanonicalIdentity,
    ProductionProjection,
    ReadinessAssessment,
    ReadinessDimension,
    ReadinessReport,
    ReadinessState,
)


def _assessment(dimension: ReadinessDimension) -> ReadinessAssessment:
    return ReadinessAssessment(
        dimension=dimension,
        state=ReadinessState.READY,
        score=100,
    )


def _readiness(asset_id: str = "CAP-LOC-001") -> ReadinessReport:
    return ReadinessReport(
        asset_id=asset_id,
        identity=_assessment(ReadinessDimension.IDENTITY),
        references=_assessment(ReadinessDimension.REFERENCES),
        generation=_assessment(ReadinessDimension.GENERATION),
        production=_assessment(ReadinessDimension.PRODUCTION),
        overall_score=100,
    )


def test_projection_is_versioned_immutable_and_checksum_is_deterministic() -> None:
    projection = ProductionProjection(
        identity=CanonicalIdentity(
            asset_id="CAP-LOC-001",
            canonical_name="Test Location",
            category=AssetCategory.LOCATION,
        ),
        canonical_description="A stable canonical location.",
        readiness=_readiness(),
        source_cap_version="1.0",
    )

    duplicate = ProductionProjection.model_validate(projection.model_dump())

    assert projection.schema_version == "2.0"
    assert projection.structured_schema_version == 1
    assert projection.production_ready is True
    assert projection.generation_ready is True
    assert projection.checksum() == duplicate.checksum()


def test_projection_rejects_readiness_for_different_asset() -> None:
    try:
        ProductionProjection(
            identity=CanonicalIdentity(
                asset_id="CAP-LOC-001",
                canonical_name="Test Location",
                category=AssetCategory.LOCATION,
            ),
            canonical_description="A stable canonical location.",
            readiness=_readiness("CAP-LOC-999"),
            source_cap_version="1.0",
        )
    except ValueError as exc:
        assert "asset IDs must match" in str(exc)
    else:
        raise AssertionError("Expected projection identity mismatch to be rejected")
