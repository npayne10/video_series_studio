"""Phase 20.19.3B: backward-compatible specification draft contract."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from vscs.application.caps.structured_specification import (
    CAPSpecificationError,
    CAPStructuredSpecification,
    CAPStructuredSpecificationService,
    SPECIFICATION_METADATA_KEY,
)
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CAPStatus


def _spec(**overrides):
    values = {
        "asset_id": "CAP-LOC-001",
        "category": AssetCategory.LOCATION,
        "design_intent": "A spatially consistent control room",
        "canonical_attributes": {"layout": "Console on the forward wall"},
        "allowed_variants": {"camera_view": ("wide", "console closeup")},
        "master_prompt": "Wide architectural master image",
    }
    values.update(overrides)
    return CAPStructuredSpecification(**values)


def test_location_specification_is_versioned_and_stable():
    spec = _spec()
    spec.validate_category_contract()
    assert spec.fingerprint() == _spec().fingerprint()
    assert len(spec.fingerprint()) == 64


def test_category_specific_fields_not_optional_for_known_categories():
    with pytest.raises(CAPSpecificationError, match="category-specific"):
        _spec(canonical_attributes={"hair": "Brown"}).validate_category_contract()


def test_locked_canonical_fields_cannot_be_variants():
    with pytest.raises(CAPSpecificationError, match="freely variable"):
        _spec(allowed_variants={"layout": ("new layout",)}).validate_category_contract()


def test_character_and_location_specs_are_distinct():
    char = _spec(
        asset_id="CAP-CHR-001",
        category=AssetCategory.CHARACTER,
        canonical_attributes={"face": "Distinct eyes and jawline"},
        allowed_variants={"pose": ("standing", "sitting")},
    )
    char.validate_category_contract()
    with pytest.raises(CAPSpecificationError):
        char.model_copy(
            update={"category": AssetCategory.LOCATION}
        ).validate_category_contract()


def test_bad_source_digest_fails_validation():
    with pytest.raises(ValidationError):
        _spec(source_document_sha256="not-sha256")


def test_save_and_load_reuses_existing_cap_metadata_without_approval():
    cap = SimpleNamespace(
        asset_id="CAP-LOC-001",
        status=CAPStatus.DRAFT,
        production_metadata={"legacy-field": "preserved"},
    )
    caps = Mock()
    caps.assets.get.return_value = SimpleNamespace(category=AssetCategory.LOCATION)
    caps.get.return_value = cap

    def update(_asset_id, changes):
        cap.production_metadata = changes.production_metadata

    caps.update.side_effect = update
    service = CAPStructuredSpecificationService(caps)
    spec = _spec()
    service.save_draft(spec)
    assert cap.production_metadata["legacy-field"] == "preserved"
    assert SPECIFICATION_METADATA_KEY in cap.production_metadata
    assert service.get("CAP-LOC-001") == spec
    assert caps.update.call_count == 1


def test_reject_cross_category_or_approved_cap_without_mutation():
    cap = SimpleNamespace(
        asset_id="CAP-LOC-001",
        status=CAPStatus.DRAFT,
        production_metadata={},
    )
    caps = Mock()
    caps.get.return_value = cap
    caps.assets.get.return_value = SimpleNamespace(category=AssetCategory.PROP)
    service = CAPStructuredSpecificationService(caps)
    with pytest.raises(CAPSpecificationError, match="category"):
        service.save_draft(_spec())
    caps.assets.get.return_value.category = AssetCategory.LOCATION
    cap.status = CAPStatus.APPROVED
    with pytest.raises(CAPSpecificationError, match="Draft"):
        service.save_draft(_spec())
    caps.update.assert_not_called()


def test_legacy_cap_without_specification_returns_none():
    caps = Mock()
    caps.get.return_value = SimpleNamespace(
        asset_id="CAP-LOC-001", production_metadata={"legacy": "unchanged"}
    )
    assert CAPStructuredSpecificationService(caps).get("CAP-LOC-001") is None


def test_stored_wrong_asset_identity_is_rejected():
    caps = Mock()
    caps.get.return_value = SimpleNamespace(
        asset_id="CAP-LOC-002",
        production_metadata={
            SPECIFICATION_METADATA_KEY: _spec().model_dump_json()
        },
    )
    with pytest.raises(CAPSpecificationError, match="identity mismatch"):
        CAPStructuredSpecificationService(caps).get("CAP-LOC-002")
