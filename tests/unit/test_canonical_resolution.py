"""Tests for CAP and canonical-reference production resolution."""

from datetime import UTC, datetime
from pathlib import Path

from vscs.application.asset_resolution import (
    CanonicalResolutionRequest,
    CanonicalResolutionService,
    CanonicalResolutionStatus,
)
from vscs.application.caps import CAPNotFoundError
from vscs.domain.caps import (
    CanonicalAssetProfile,
    CanonicalReference,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CAPStatus,
)


class _Caps:
    def __init__(self, cap: CanonicalAssetProfile | None) -> None:
        self.cap = cap

    def get(self, asset_id: str) -> CanonicalAssetProfile:
        if self.cap is None:
            raise CAPNotFoundError(asset_id)
        return self.cap


class _References:
    def __init__(self, references: tuple[CanonicalReference, ...]) -> None:
        self.references = references

    def list_for_cap(
        self,
        asset_id: str,
        **_kwargs: object,
    ) -> tuple[CanonicalReference, ...]:
        return self.references


def _cap(status: CAPStatus = CAPStatus.APPROVED) -> CanonicalAssetProfile:
    now = datetime.now(UTC)
    return CanonicalAssetProfile(
        id=1,
        asset_id="CAP-SHP-IRON-HORIZON",
        title="Iron Horizon",
        version="2.0",
        status=status,
        canonical_description="A 145 metre Guild survey spacecraft.",
        visual_identity="Four rear fusion engines.",
        production_notes="Controlled blue-white engine trails.",
        reference_paths=(),
        created_at=now,
        updated_at=now,
    )


def _reference(
    reference_id: int,
    role: CanonicalReferenceRole,
    reference_type: CanonicalReferenceType = CanonicalReferenceType.IMAGE,
) -> CanonicalReference:
    now = datetime.now(UTC)
    return CanonicalReference(
        id=reference_id,
        cap_id=1,
        reference_type=reference_type,
        role=role,
        title=f"Reference {reference_id}",
        file_path=Path(f"references/{reference_id}.png"),
        description="Approved production reference.",
        notes="Stable canonical view.",
        version="1.0",
        status=CanonicalReferenceStatus.APPROVED,
        approved_by="Neill",
        approved_at=now,
        locked=True,
        created_at=now,
        updated_at=now,
    )


def test_resolves_approved_cap_and_selects_primary_reference() -> None:
    service = CanonicalResolutionService(
        _Caps(_cap()),  # type: ignore[arg-type]
        _References(
            (
                _reference(9, CanonicalReferenceRole.SECONDARY),
                _reference(7, CanonicalReferenceRole.PRIMARY),
            )
        ),  # type: ignore[arg-type]
    )

    first = service.resolve(CanonicalResolutionRequest("cap-shp-iron-horizon"))
    second = service.resolve(first.request)

    assert first.status is CanonicalResolutionStatus.READY
    assert first.primary_reference is not None
    assert first.primary_reference.reference_id == "7"
    assert tuple(
        reference.reference_id for reference in first.references
    ) == ("7", "9")
    assert first.fingerprint is not None
    assert first.fingerprint.checksum == second.fingerprint.checksum


def test_missing_primary_reference_is_partial() -> None:
    service = CanonicalResolutionService(
        _Caps(_cap()),  # type: ignore[arg-type]
        _References(
            (_reference(9, CanonicalReferenceRole.SECONDARY),)
        ),  # type: ignore[arg-type]
    )

    result = service.resolve(CanonicalResolutionRequest("CAP-SHP-IRON-HORIZON"))

    assert result.status is CanonicalResolutionStatus.PARTIAL
    assert result.primary_reference is None
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "reference.primary_missing"
    }


def test_reference_filters_and_minimum_count_are_enforced() -> None:
    service = CanonicalResolutionService(
        _Caps(_cap()),  # type: ignore[arg-type]
        _References(
            (
                _reference(7, CanonicalReferenceRole.PRIMARY),
                _reference(
                    8,
                    CanonicalReferenceRole.SECONDARY,
                    CanonicalReferenceType.DOCUMENT,
                ),
            )
        ),  # type: ignore[arg-type]
    )

    result = service.resolve(
        CanonicalResolutionRequest(
            "CAP-SHP-IRON-HORIZON",
            minimum_approved_references=2,
            reference_types=frozenset({CanonicalReferenceType.IMAGE}),
        )
    )

    assert result.status is CanonicalResolutionStatus.PARTIAL
    assert tuple(
        reference.reference_id for reference in result.references
    ) == ("7",)
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "reference.minimum_not_met"
    }


def test_missing_cap_is_unresolved() -> None:
    service = CanonicalResolutionService(
        _Caps(None),  # type: ignore[arg-type]
        _References(()),  # type: ignore[arg-type]
    )

    result = service.resolve(CanonicalResolutionRequest("UNKNOWN"))

    assert result.status is CanonicalResolutionStatus.UNRESOLVED
    assert result.cap is None
    assert result.diagnostics[0].code == "cap.not_found"
