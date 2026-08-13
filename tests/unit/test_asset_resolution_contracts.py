"""Tests for Phase 17.5.1 asset-resolution contracts."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from vscs.application.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionService,
    AssetResolutionStatus,
)
from vscs.application.assets import AssetNotFoundError
from vscs.application.caps import CAPNotFoundError
from vscs.domain.assets import Asset, AssetCategory, AssetStatus
from vscs.domain.caps import (
    CanonicalAssetProfile,
    CanonicalReference,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CanonicalReferenceView,
    CAPStatus,
    ProductionReference,
)


class _Assets:
    def __init__(self, asset: Asset | None) -> None:
        self.asset = asset

    def get(self, asset_id: str) -> Asset:
        if self.asset is None:
            raise AssetNotFoundError(asset_id)
        return self.asset


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

    def list_for_cap(self, asset_id: str, **_kwargs: object) -> tuple[CanonicalReference, ...]:
        return self.references


class _ProductionProjections:
    def __init__(self, references: tuple[ProductionReference, ...]) -> None:
        self.references = references

    def project(self, asset_id: str) -> SimpleNamespace:
        return SimpleNamespace(references=self.references)


def _asset() -> Asset:
    now = datetime.now(UTC)
    return Asset(
        id=1,
        asset_id="CAP-SHP-IRON-HORIZON",
        name="Iron Horizon",
        category=AssetCategory.SHIP,
        description="Guild survey spacecraft.",
        status=AssetStatus.APPROVED,
        file_path=None,
        tags=("guild", "ship"),
        created_at=now,
        updated_at=now,
    )


def _cap() -> CanonicalAssetProfile:
    now = datetime.now(UTC)
    return CanonicalAssetProfile(
        id=1,
        asset_id="CAP-SHP-IRON-HORIZON",
        title="Iron Horizon",
        version="2.0",
        status=CAPStatus.APPROVED,
        canonical_description="A 145 metre Guild survey spacecraft.",
        visual_identity="Four rear fusion engines.",
        production_notes="Engine trails are controlled blue-white.",
        reference_paths=(),
        created_at=now,
        updated_at=now,
    )


def _reference() -> CanonicalReference:
    now = datetime.now(UTC)
    return CanonicalReference(
        id=7,
        cap_id=1,
        file_path=Path("references/iron_horizon.png"),
        reference_type=CanonicalReferenceType.IMAGE,
        role=CanonicalReferenceRole.PRIMARY,
        title="Iron Horizon starboard reference",
        description="Approved canonical starboard view.",
        notes="Use for hull and engine placement.",
        version="1.0",
        status=CanonicalReferenceStatus.APPROVED,
        approved_by="Neill",
        approved_at=now,
        locked=True,
        created_at=now,
        updated_at=now,
    )


def _production_reference() -> ProductionReference:
    return ProductionReference(
        reference_id="MASTER-7",
        family=CanonicalReferenceFamily.MASTER,
        view=CanonicalReferenceView.MASTER,
        origin=CanonicalReferenceOrigin.CHATGPT_MASTER,
        lifecycle=CanonicalReferenceLifecycle.LOCKED,
        file_path="references/iron_horizon.png",
        approved_by="Neill",
    )


def test_complete_asset_resolution_produces_stable_fingerprint() -> None:
    resolver = AssetResolutionService(
        _Assets(_asset()),  # type: ignore[arg-type]
        _Caps(_cap()),  # type: ignore[arg-type]
        _References((_reference(),)),  # type: ignore[arg-type]
        _ProductionProjections((_production_reference(),)),  # type: ignore[arg-type]
    )

    first = resolver.resolve(
        AssetResolutionRequest(
            "cap-shp-iron-horizon",
            expected_category=AssetCategory.SHIP,
        )
    )
    second = resolver.resolve(first.request)

    assert first.status is AssetResolutionStatus.RESOLVED
    assert first.asset is not None
    assert first.cap is not None
    assert first.references[0].reference_id == "MASTER-7"
    assert first.references[0].role == "primary"
    assert first.references[0].file_path == "references/iron_horizon.png"
    assert first.fingerprint is not None
    assert second.fingerprint is not None
    assert first.fingerprint.checksum == second.fingerprint.checksum


def test_missing_cap_returns_partial_resolution() -> None:
    resolver = AssetResolutionService(
        _Assets(_asset()),  # type: ignore[arg-type]
        _Caps(None),  # type: ignore[arg-type]
        _References(()),  # type: ignore[arg-type]
    )

    result = resolver.resolve(AssetResolutionRequest("CAP-SHP-IRON-HORIZON"))

    assert result.status is AssetResolutionStatus.PARTIAL
    assert result.asset is not None
    assert result.cap is None
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"cap.not_found"}


def test_missing_asset_is_unresolved() -> None:
    resolver = AssetResolutionService(
        _Assets(None),  # type: ignore[arg-type]
        _Caps(None),  # type: ignore[arg-type]
        _References(()),  # type: ignore[arg-type]
    )

    result = resolver.resolve(AssetResolutionRequest("UNKNOWN"))

    assert result.status is AssetResolutionStatus.UNRESOLVED
    assert result.asset is None
    assert result.diagnostics[0].code == "asset.not_found"


def test_resolve_many_is_deterministically_ordered() -> None:
    resolver = AssetResolutionService(
        _Assets(None),  # type: ignore[arg-type]
        _Caps(None),  # type: ignore[arg-type]
        _References(()),  # type: ignore[arg-type]
    )

    results = resolver.resolve_many(
        (AssetResolutionRequest("Z-ASSET"), AssetResolutionRequest("A-ASSET"))
    )

    assert tuple(result.request.asset_id for result in results) == (
        "A-ASSET",
        "Z-ASSET",
    )
