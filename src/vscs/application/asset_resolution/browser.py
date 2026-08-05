"""Resolution-aware browsing and selection for production assets."""

from __future__ import annotations

from dataclasses import dataclass

from vscs.application.assets import AssetService
from vscs.domain.assets import AssetCategory, AssetStatus

from .canonical import (
    CanonicalResolutionRequest,
    CanonicalResolutionResult,
    CanonicalResolutionService,
    CanonicalResolutionStatus,
)
from .models import (
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionStatus,
)
from .resolver import AssetResolutionService


@dataclass(frozen=True, slots=True)
class AssetBrowserFilter:
    """Stable filter policy for one asset-browser query."""

    query: str = ""
    categories: frozenset[AssetCategory] = frozenset()
    statuses: frozenset[AssetStatus] = frozenset()
    resolution_statuses: frozenset[AssetResolutionStatus] = frozenset()
    require_cap: bool = False
    require_approved_references: bool = False


@dataclass(frozen=True, slots=True)
class AssetBrowserItem:
    """One display-safe asset row with canonical readiness metadata."""

    asset_id: str
    name: str
    category: AssetCategory
    asset_status: AssetStatus
    description: str
    tags: tuple[str, ...]
    resolution: AssetResolutionResult
    canonical: CanonicalResolutionResult | None = None

    @property
    def resolution_status(self) -> AssetResolutionStatus:
        return self.resolution.status

    @property
    def cap_version(self) -> str | None:
        return self.resolution.cap.version if self.resolution.cap is not None else None

    @property
    def approved_reference_count(self) -> int:
        return len(self.resolution.references)

    @property
    def primary_reference_id(self) -> str | None:
        if self.canonical is None or self.canonical.primary_reference is None:
            return None
        return self.canonical.primary_reference.reference_id

    @property
    def selectable(self) -> bool:
        return self.resolution.status is not AssetResolutionStatus.UNRESOLVED


@dataclass(frozen=True, slots=True)
class AssetBrowserResult:
    """Immutable results for one browser query."""

    filter: AssetBrowserFilter
    items: tuple[AssetBrowserItem, ...]
    total_assets: int


@dataclass(slots=True)
class AssetBrowserService:
    """Browse project assets and attach authoritative resolution status."""

    assets: AssetService
    resolver: AssetResolutionService
    canonical: CanonicalResolutionService | None = None

    def browse(self, filter_: AssetBrowserFilter | None = None) -> AssetBrowserResult:
        selected = filter_ or AssetBrowserFilter()
        assets = self.assets.list()
        items: list[AssetBrowserItem] = []
        for asset in assets:
            if selected.categories and asset.category not in selected.categories:
                continue
            if selected.statuses and asset.status not in selected.statuses:
                continue
            if not self._matches_query(asset, selected.query):
                continue
            resolution = self.resolver.resolve(
                AssetResolutionRequest(
                    asset.asset_id,
                    expected_category=asset.category,
                    require_cap=selected.require_cap,
                    require_approved_references=selected.require_approved_references,
                )
            )
            if (
                selected.resolution_statuses
                and resolution.status not in selected.resolution_statuses
            ):
                continue
            canonical = (
                self.canonical.resolve(
                    CanonicalResolutionRequest(
                        asset.asset_id,
                        require_approved_cap=selected.require_cap,
                        require_primary_reference=selected.require_approved_references,
                        minimum_approved_references=(
                            1 if selected.require_approved_references else 0
                        ),
                    )
                )
                if self.canonical is not None
                else None
            )
            if (
                selected.require_approved_references
                and canonical is not None
                and canonical.status is not CanonicalResolutionStatus.READY
            ):
                continue
            items.append(
                AssetBrowserItem(
                    asset.asset_id,
                    asset.name,
                    asset.category,
                    asset.status,
                    asset.description,
                    asset.tags,
                    resolution,
                    canonical,
                )
            )
        ordered = tuple(
            sorted(items, key=lambda item: (item.name.casefold(), item.asset_id))
        )
        return AssetBrowserResult(selected, ordered, len(assets))

    def select(
        self,
        asset_id: str,
        *,
        expected_category: AssetCategory | None = None,
        require_cap: bool = False,
        require_approved_references: bool = False,
    ) -> AssetResolutionResult:
        """Resolve one browser selection using explicit production requirements."""
        return self.resolver.resolve(
            AssetResolutionRequest(
                asset_id,
                expected_category=expected_category,
                require_cap=require_cap,
                require_approved_references=require_approved_references,
            )
        )

    @staticmethod
    def _matches_query(asset: object, query: str) -> bool:
        normalized = query.strip().casefold()
        if not normalized:
            return True
        searchable = " ".join(
            (
                asset.asset_id,
                asset.name,
                asset.description,
                asset.category.value,
                *asset.tags,
            )
        ).casefold()
        return normalized in searchable
