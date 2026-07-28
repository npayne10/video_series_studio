"""Tests for the Canonical Asset Intelligence Engine."""

from datetime import UTC, datetime

from vscs.application.caie import CanonicalAssetIntelligenceEngine, CanonicalPromptContext
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.domain.caps import CanonicalAssetProfile, CAPStatus


def _ship_context() -> CanonicalPromptContext:
    now = datetime.now(UTC)
    asset = Asset(
        id=4,
        asset_id="CAP-SHP-004",
        name="Guild Tug Ship",
        category=AssetCategory.SHIP,
        description="Utility ship",
        status=AssetStatus.DRAFT,
        file_path=None,
        tags=("guild", "utility"),
        created_at=now,
        updated_at=now,
    )
    profile = CanonicalAssetProfile(
        id=4,
        asset_id="CAP-SHP-004",
        title="Guild Tug Ship",
        version="1.0",
        status=CAPStatus.DRAFT,
        canonical_description="Story Role: The Guild Tug Ship will pull the Mauritania out of the orbital dock.",
        visual_identity="Compact industrial Guild vessel with towing clamps and manoeuvring thrusters.",
        production_notes="No visible text or labels.",
        reference_paths=(),
        created_at=now,
        updated_at=now,
    )
    return CanonicalPromptContext(asset=asset, profile=profile)


def test_caie_disambiguates_space_tug_from_maritime_tug() -> None:
    package = CanonicalAssetIntelligenceEngine().compile(_ship_context())

    assert "orbital spacecraft" in package.positive_prompt
    assert "operating in vacuum" in package.positive_prompt
    assert "not a terrestrial maritime vessel" in package.positive_prompt
    assert "harbour tug" in package.negative_prompt
    assert "ocean" in package.negative_prompt


def test_caie_removes_metadata_labels_and_blocks_visible_text() -> None:
    package = CanonicalAssetIntelligenceEngine().compile(_ship_context())

    assert "Story Role:" not in package.positive_prompt
    assert "CAP-SHP-004" not in package.positive_prompt
    assert "Do not render CAP metadata" in package.positive_prompt
    assert "title card" in package.negative_prompt
