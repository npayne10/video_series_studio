"""Phase 20.19.3B.1 — test actual SQLite CAP repository persistence.

The database is transient and exists only under pytest's tmp_path.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from vscs.application.caps.repository import CAPRepository
from vscs.application.caps.service import CAPService
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPSpecificationError,
    CAPStructuredSpecification,
    CAPStructuredSpecificationService,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPCreate, CAPStatus, CAPUpdate
from vscs.infrastructure.database.manager import DatabaseManager
from vscs.infrastructure.database.models import AssetRecord, Base


@pytest.fixture
def cap_services(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'specification.db').as_posix()}")
    Base.metadata.create_all(engine)
    database = DatabaseManager()
    database.engine = engine
    database._session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    assets = Mock()
    assets.projects.project_directory = tmp_path
    assets.projects.is_project_open = True
    categories = {
        "CAP-LOC-001": AssetCategory.LOCATION,
        "CAP-CHR-001": AssetCategory.CHARACTER,
    }
    assets.get.side_effect = lambda asset_id: SimpleNamespace(
        asset_id=asset_id, category=categories[asset_id]
    )
    with database.session() as session:
        for asset_id, category in categories.items():
            session.add(
                AssetRecord(
                    asset_id=asset_id,
                    name=asset_id,
                    category=category.value,
                    status="draft",
                    description="fixture",
                )
            )
    caps = CAPService(assets, CAPRepository(database))
    for asset_id in categories:
        caps.create(
            CAPCreate(
                asset_id=asset_id,
                title=asset_id,
                canonical_description="Unapproved identity",
                production_metadata={"legacy": "kept"},
            )
        )
    try:
        yield caps, database
    finally:
        database.close()


def _spec(asset_id, category, key, value):
    return CAPStructuredSpecification(
        asset_id=asset_id,
        category=category,
        design_intent="Visual continuity",
        canonical_attributes={key: value},
        allowed_variants={"camera": ("wide", "close")},
        master_prompt="Production reference image",
        continuity_rules=("Keep identity stable",),
        source_document_sha256="a" * 64,
    )


def test_round_trip_sqlite_retains_legacy_metadata_and_revision(cap_services):
    caps, database = cap_services
    service = CAPStructuredSpecificationService(caps)
    spec = _spec("CAP-LOC-001", AssetCategory.LOCATION, "layout", "Fixed room geometry")
    service.save_draft(spec)
    database.engine.dispose()
    new_repository = CAPRepository(database)
    new_caps = CAPService(caps.assets, new_repository)
    loaded = CAPStructuredSpecificationService(new_caps).get("CAP-LOC-001")
    assert loaded == spec
    stored = new_caps.get("CAP-LOC-001")
    assert stored.production_metadata["legacy"] == "kept"
    assert SPECIFICATION_METADATA_KEY in stored.production_metadata
    assert stored.status == CAPStatus.DRAFT


def test_project_asset_identity_and_categories_are_isolated(cap_services):
    caps, _ = cap_services
    service = CAPStructuredSpecificationService(caps)
    service.save_draft(
        _spec("CAP-LOC-001", AssetCategory.LOCATION, "layout", "Unchanging room")
    )
    service.save_draft(
        _spec("CAP-CHR-001", AssetCategory.CHARACTER, "face", "Distinct anatomy")
    )
    assert service.get("CAP-LOC-001").category == AssetCategory.LOCATION
    assert service.get("CAP-CHR-001").category == AssetCategory.CHARACTER
    assert service.get("CAP-LOC-001").fingerprint() != service.get("CAP-CHR-001").fingerprint()


def test_approved_cap_cannot_be_mutated_by_specification_service(cap_services):
    caps, _ = cap_services
    service = CAPStructuredSpecificationService(caps)
    caps.update("CAP-LOC-001", CAPUpdate(status=CAPStatus.APPROVED))
    with pytest.raises(CAPSpecificationError, match="Draft"):
        service.save_draft(
            _spec("CAP-LOC-001", AssetCategory.LOCATION, "layout", "New layout")
        )
    assert service.get("CAP-LOC-001") is None


def test_missing_or_wrong_category_is_refused_before_persistence(cap_services):
    caps, _ = cap_services
    service = CAPStructuredSpecificationService(caps)
    with pytest.raises(CAPSpecificationError, match="category"):
        service.save_draft(
            _spec("CAP-LOC-001", AssetCategory.PROP, "geometry", "Console")
        )
    assert service.get("CAP-LOC-001") is None


def test_legacy_cap_remains_readable_without_structured_record(cap_services):
    caps, _ = cap_services
    assert CAPStructuredSpecificationService(caps).get("CAP-LOC-001") is None
    assert caps.get("CAP-LOC-001").production_metadata == {"legacy": "kept"}
