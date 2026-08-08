"""Unit tests for Phase 18.2.11.2.3 reference-library domain models."""

import pytest
from pydantic import ValidationError

from vscs.domain.caps import (
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
    ReferenceLibraryEntry,
    ReferenceLibrarySnapshot,
)


def _master(record_id: int = 1) -> ReferenceLibraryEntry:
    return ReferenceLibraryEntry(
        reference_record_id=record_id,
        asset_id="CAP-SHP-004",
        reference_id=f"CAP-SHP-004-REF-{record_id:04d}",
        family=CanonicalReferenceFamily.MASTER,
        view=CanonicalReferenceView.MASTER,
        origin=CanonicalReferenceOrigin.CHATGPT_MASTER,
    )


def test_master_entry_requires_chatgpt_origin_and_no_parent() -> None:
    master = _master()

    assert master.origin is CanonicalReferenceOrigin.CHATGPT_MASTER
    assert master.parent_reference_id is None
    assert master.lifecycle is CanonicalReferenceLifecycle.CANDIDATE

    with pytest.raises(ValidationError, match="originate from ChatGPT"):
        ReferenceLibraryEntry(
            reference_record_id=2,
            asset_id="CAP-SHP-004",
            reference_id="CAP-SHP-004-REF-0002",
            family=CanonicalReferenceFamily.MASTER,
            view=CanonicalReferenceView.MASTER,
            origin=CanonicalReferenceOrigin.VSCS_DERIVED,
            parent_reference_id="CAP-SHP-004-REF-0001",
        )


def test_vscs_derived_entry_requires_parent_master_identity() -> None:
    with pytest.raises(ValidationError, match="require the MASTER parent"):
        ReferenceLibraryEntry(
            reference_record_id=2,
            asset_id="CAP-SHP-004",
            reference_id="CAP-SHP-004-REF-0002",
            family=CanonicalReferenceFamily.PRODUCTION_VIEW,
            view=CanonicalReferenceView.TOP,
            origin=CanonicalReferenceOrigin.VSCS_DERIVED,
            generator="test-generator",
        )


def test_snapshot_rejects_duplicate_record_and_reference_ids() -> None:
    master = _master()

    with pytest.raises(ValidationError, match="record IDs must be unique"):
        ReferenceLibrarySnapshot(entries=(master, master.model_copy()))

    duplicate_reference_id = _master(2).model_copy(update={"reference_id": master.reference_id})
    with pytest.raises(ValidationError, match="reference IDs must be unique"):
        ReferenceLibrarySnapshot(entries=(master, duplicate_reference_id))
