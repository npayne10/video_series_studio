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
    assert caps.list() == ()
