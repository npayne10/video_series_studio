"""Tests for CAIE v2 category and archetype intelligence."""

from datetime import UTC, datetime

from vscs.application.caie import (
    CAIEKnowledgeBase,
    CanonicalAssetIntelligenceEngine,
    CanonicalPromptContext,
)
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.domain.caps import CAPStatus, CanonicalAssetProfile


def _context(title: str = "Guild Tug Ship") -> CanonicalPromptContext:
    now = datetime.now(UTC)
    asset = Asset(
        id=4,
        asset_id="CAP-SHP-004",
        name=title,
        category=AssetCategory.SHIP,
        description="Orbital utility craft",
        status=AssetStatus.DRAFT,
        file_path=None,
        tags=("guild", "utility"),
        created_at=now,
        updated_at=now,
    )
    profile = CanonicalAssetProfile(
        id=4,
        asset_id="CAP-SHP-004",
        title=title,
        version="1.0",
        status=CAPStatus.DRAFT,
        canonical_description="The Guild Tug Ship pulls the Mauritania out of the orbital landing bay.",
        visual_identity="No final hull design or markings are approved.",
        production_notes="Do not establish unsupported canon.",
        reference_paths=(),
        created_at=now,
        updated_at=now,
    )
    return CanonicalPromptContext(asset=asset, profile=profile)


def test_knowledge_base_resolves_orbital_tug_archetype() -> None:
    knowledge = CAIEKnowledgeBase().resolve(
        category=AssetCategory.SHIP,
        title="Guild Tug Ship",
        description="Orbital utility craft",
    )

    assert knowledge.knowledge_id == "ships/orbital_tug"
    assert "marine wheelhouse" in " ".join(knowledge.forbidden_features)
    assert "reaction-control thrusters" in knowledge.required_anchors


def test_caie_v2_injects_engineering_and_forbidden_archetypes() -> None:
    package = CanonicalAssetIntelligenceEngine().compile(_context())

    assert package.engine_version == "2.0"
    assert package.knowledge_id == "ships/orbital_tug"
    assert "Engineering logic:" in package.positive_prompt
    assert "Forbidden archetypes and interpretations:" in package.positive_prompt
    assert "harbour tugboat" in package.negative_prompt
    assert "waterline" in package.negative_prompt
    assert "reaction-control thrusters" in package.positive_prompt


def test_legacy_style_name_resolves_to_xorix_style() -> None:
    context = _context()
    context = CanonicalPromptContext(
        asset=context.asset,
        profile=context.profile,
        style_profile="grounded_cinematic",
    )
    package = CanonicalAssetIntelligenceEngine().compile(context)

    assert package.style_profile == "grounded_cinematic"
    assert "premium streaming television production reference" in package.positive_prompt
