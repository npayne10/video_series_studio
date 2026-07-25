"""Tests for automated Canonical Asset Profile generation."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetRepository, AssetService
from vscs.application.caps import (
    CAPGenerationError,
    CAPGeneratorService,
    CAPRepository,
    CAPService,
)
from vscs.application.projects import ProjectService
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPStatus
from vscs.domain.caps.generation import (
    CAPSectionConfidence,
    ExtractedCanonicalFact,
    GeneratedCAPDraft,
)
from vscs.infrastructure.ai import TemplateCAPGenerationProvider
from vscs.infrastructure.configuration import ConfigurationService
from vscs.infrastructure.database import DatabaseManager


def build_generator(tmp_path: Path) -> tuple[CAPGeneratorService, CAPService, AssetService]:
    configuration = ConfigurationService(tmp_path / "config" / "settings.yaml")
    configuration.load()
    database = DatabaseManager()
    projects = ProjectService(configuration, database)
    assets = AssetService(projects, AssetRepository(database))
    caps = CAPService(assets, CAPRepository(database))
    generator = CAPGeneratorService(assets, caps, TemplateCAPGenerationProvider())
    projects.create(tmp_path / "Example", name="Example")
    return generator, caps, assets


def test_generate_and_create_cap_from_story_context(tmp_path: Path) -> None:
    generator, caps, assets = build_generator(tmp_path)
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-001",
            name="Iron Horizon",
            category=AssetCategory.SHIP,
            description="A compact Guild survey vessel.",
        )
    )

    generated = generator.generate_and_create(
        "CAP-SHP-001",
        "The Iron Horizon descended through the atmosphere under precise control.",
    )

    assert generated.status is CAPStatus.DRAFT
    stored = caps.get("CAP-SHP-001")
    assert stored.title == "Iron Horizon"
    assert "precise control" in stored.canonical_description
    assert "Continuity rules" in stored.production_notes
    assert "Extracted canonical facts" in stored.production_notes
    assert "AI confidence scores" in stored.production_notes


def test_create_from_reviewed_draft_preserves_moderator_edits(tmp_path: Path) -> None:
    generator, caps, assets = build_generator(tmp_path)
    assets.create(
        AssetCreate(
            asset_id="CAP-CHR-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
        )
    )
    reviewed = GeneratedCAPDraft(
        title="Commander James Spence",
        canonical_description="A disciplined Guild commander.",
        visual_identity="Grey-blue eyes and a restrained command presence.",
        production_notes="Use the approved uniform reference.",
        continuity_rules=("Maintain his established age and rank.",),
        prohibited_variations=("Do not change his eye colour.",),
        unresolved_questions=("Confirm the final command insignia.",),
        source_summary="Reviewed against the approved manuscript passage.",
        canonical_facts=(
            ExtractedCanonicalFact(
                fact="James is a Guild commander.",
                evidence="The source addresses him as Commander James Spence.",
                confidence=0.98,
            ),
        ),
        confidence=CAPSectionConfidence(
            canonical_description=0.95,
            visual_identity=0.8,
            production_notes=0.85,
            continuity_rules=0.9,
            prohibited_variations=0.9,
            overall=0.88,
        ),
    )

    generator.create_from_draft("CAP-CHR-001", reviewed)

    stored = caps.get("CAP-CHR-001")
    assert stored.status is CAPStatus.DRAFT
    assert stored.canonical_description == reviewed.canonical_description
    assert "Do not change his eye colour" in stored.production_notes
    assert "Confirm the final command insignia" in stored.production_notes
    assert "James is a Guild commander" in stored.production_notes
    assert "Overall: 88%" in stored.production_notes


def test_generation_requires_story_context(tmp_path: Path) -> None:
    generator, _, assets = build_generator(tmp_path)
    assets.create(
        AssetCreate(
            asset_id="CAP-CHR-001",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
        )
    )

    with pytest.raises(CAPGenerationError):
        generator.generate_draft("CAP-CHR-001", "   ")


def test_generate_draft_does_not_persist_cap(tmp_path: Path) -> None:
    generator, caps, assets = build_generator(tmp_path)
    assets.create(
        AssetCreate(
            asset_id="CAP-LOC-001",
            name="Kestrel Nine",
            category=AssetCategory.LOCATION,
        )
    )

    draft = generator.generate_draft(
        "CAP-LOC-001",
        "Kestrel Nine was a civilian relay station assembled across several decades.",
    )

    assert draft.title == "Kestrel Nine"
    assert draft.canonical_facts
    assert draft.unresolved_questions
    assert 0.0 <= draft.confidence.overall <= 1.0
    assert caps.list() == ()
