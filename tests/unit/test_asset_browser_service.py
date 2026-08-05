"""Tests for resolution-aware asset browsing and selection."""

from datetime import UTC, datetime

from vscs.application.asset_resolution import (
    AssetBrowserFilter,
    AssetBrowserService,
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionStatus,
    ResolvedAssetBinding,
)
from vscs.domain.assets import Asset, AssetCategory, AssetStatus


class _Assets:
    def __init__(self, assets: tuple[Asset, ...]) -> None:
        self._assets = assets

    def list(self) -> tuple[Asset, ...]:
        return self._assets


class _Resolver:
    def resolve(self, request: AssetResolutionRequest) -> AssetResolutionResult:
        asset = next(asset for asset in _assets() if asset.asset_id == request.asset_id)
        binding = ResolvedAssetBinding(
            asset.asset_id,
            asset.name,
            asset.category,
            asset.description,
            asset.status,
            asset.tags,
            f"checksum-{asset.asset_id}",
        )
        status = (
            AssetResolutionStatus.RESOLVED
            if asset.status is AssetStatus.APPROVED
            else AssetResolutionStatus.PARTIAL
        )
        return AssetResolutionResult(request, status, asset=binding)


def _assets() -> tuple[Asset, ...]:
    now = datetime.now(UTC)
    return (
        Asset(
            id=1,
            asset_id="SHP-IRON-HORIZON",
            name="Iron Horizon",
            category=AssetCategory.SHIP,
            description="Guild survey spacecraft",
            status=AssetStatus.APPROVED,
            file_path=None,
            tags=("guild", "ship"),
            created_at=now,
            updated_at=now,
        ),
        Asset(
            id=2,
            asset_id="CHR-JAMES",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            description="Guild commander",
            status=AssetStatus.DRAFT,
            file_path=None,
            tags=("guild", "commander"),
            created_at=now,
            updated_at=now,
        ),
    )


def test_browser_filters_and_orders_resolution_aware_items() -> None:
    browser = AssetBrowserService(
        _Assets(_assets()),  # type: ignore[arg-type]
        _Resolver(),  # type: ignore[arg-type]
    )

    result = browser.browse(
        AssetBrowserFilter(
            categories=frozenset({AssetCategory.SHIP}),
            statuses=frozenset({AssetStatus.APPROVED}),
        )
    )

    assert result.total_assets == 2
    assert tuple(item.asset_id for item in result.items) == ("SHP-IRON-HORIZON",)
    assert result.items[0].resolution_status is AssetResolutionStatus.RESOLVED
    assert result.items[0].selectable


def test_browser_searches_tags_and_can_filter_resolution_status() -> None:
    browser = AssetBrowserService(
        _Assets(_assets()),  # type: ignore[arg-type]
        _Resolver(),  # type: ignore[arg-type]
    )

    result = browser.browse(
        AssetBrowserFilter(
            query="commander",
            resolution_statuses=frozenset({AssetResolutionStatus.PARTIAL}),
        )
    )

    assert tuple(item.asset_id for item in result.items) == ("CHR-JAMES",)
    assert result.items[0].resolution_status is AssetResolutionStatus.PARTIAL
