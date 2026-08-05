"""Tests for asset dependency indexing and change propagation."""

from dataclasses import dataclass

from vscs.application.asset_resolution import (
    AssetChangePropagationService,
    AssetDependencyChangeKind,
    AssetDependencyIndex,
    PromptAssetDependency,
    PromptAssetEnrichmentRequest,
    PromptAssetEnrichmentResult,
)


@dataclass
class _Enrichment:
    result: PromptAssetEnrichmentResult

    def enrich(self, request: PromptAssetEnrichmentRequest) -> PromptAssetEnrichmentResult:
        return PromptAssetEnrichmentResult(
            request,
            self.result.sources,
            self.result.canonical_asset_ids,
            self.result.reference_ids,
            self.result.dependencies,
            self.result.diagnostics,
        )


class _History:
    def all(self) -> tuple[object, ...]:
        return ()

    def invalidate_item(self, item_id: str) -> bool:
        return False


def _result(cap_checksum: str = "cap-1") -> PromptAssetEnrichmentResult:
    request = PromptAssetEnrichmentRequest(
        "SHOT-001",
        ("SHP-IRON-HORIZON",),
    )
    return PromptAssetEnrichmentResult(
        request,
        (),
        ("SHP-IRON-HORIZON",),
        ("7",),
        (
            PromptAssetDependency(
                "SHP-IRON-HORIZON",
                "asset-1",
                cap_checksum,
                ("reference-1",),
            ),
        ),
    )


def test_dependency_index_returns_affected_shots() -> None:
    index = AssetDependencyIndex()
    index.register(_result())

    assert index.affected_shots("shp-iron-horizon") == ("SHOT-001",)
    assert index.affected_shots("UNKNOWN") == ()


def test_cap_change_refreshes_shot_and_reports_change() -> None:
    index = AssetDependencyIndex()
    index.register(_result("cap-1"))
    service = AssetChangePropagationService(
        index,
        _Enrichment(_result("cap-2")),  # type: ignore[arg-type]
        _History(),  # type: ignore[arg-type]
    )

    report = service.propagate("SHP-IRON-HORIZON")

    assert report.changed
    assert report.affected_shot_ids == ("SHOT-001",)
    assert report.refreshed_shot_ids == ("SHOT-001",)
    assert report.changes[0].kinds == (AssetDependencyChangeKind.CAP,)


def test_unchanged_dependency_does_not_invalidate() -> None:
    index = AssetDependencyIndex()
    original = _result()
    index.register(original)
    service = AssetChangePropagationService(
        index,
        _Enrichment(original),  # type: ignore[arg-type]
        _History(),  # type: ignore[arg-type]
    )

    report = service.propagate("SHP-IRON-HORIZON")

    assert not report.changed
    assert report.invalidated_item_ids == ()
