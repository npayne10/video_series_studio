"""Tests for authoritative asset enrichment of Prompt Graph sources."""

from vscs.application.asset_resolution import (
    AssetResolutionRequest,
    AssetResolutionResult,
    AssetResolutionStatus,
    CanonicalReferenceBinding,
    CanonicalResolutionRequest,
    CanonicalResolutionResult,
    CanonicalResolutionStatus,
    PromptAssetEnrichmentRequest,
    PromptGraphAssetEnrichmentService,
    ResolvedAssetBinding,
    ResolvedCAPBinding,
)
from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphDiagnosticsFactory,
    PromptGraphResolver,
    PromptNodeKind,
)
from vscs.domain.assets import AssetCategory, AssetStatus
from vscs.domain.caps import (
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CAPStatus,
)


class _Assets:
    def resolve(self, request: AssetResolutionRequest) -> AssetResolutionResult:
        asset = ResolvedAssetBinding(
            request.asset_id,
            "Iron Horizon",
            AssetCategory.SHIP,
            "Guild survey spacecraft.",
            AssetStatus.APPROVED,
            ("guild", "ship"),
            "asset-checksum",
        )
        cap = ResolvedCAPBinding(
            request.asset_id,
            "Iron Horizon",
            "2.0",
            CAPStatus.APPROVED,
            "A 145 metre Guild survey spacecraft.",
            "Four rear fusion engines.",
            "Controlled blue-white engine trails.",
            "cap-checksum",
        )
        return AssetResolutionResult(
            request,
            AssetResolutionStatus.RESOLVED,
            asset,
            cap,
        )


class _Canonical:
    def resolve(
        self,
        request: CanonicalResolutionRequest,
    ) -> CanonicalResolutionResult:
        cap = ResolvedCAPBinding(
            request.asset_id,
            "Iron Horizon",
            "2.0",
            CAPStatus.APPROVED,
            "A 145 metre Guild survey spacecraft.",
            "Four rear fusion engines.",
            "Controlled blue-white engine trails.",
            "cap-checksum",
        )
        reference = CanonicalReferenceBinding(
            "7",
            "Primary starboard view",
            "references/iron_horizon.png",
            CanonicalReferenceType.IMAGE,
            CanonicalReferenceRole.PRIMARY,
            "1.0",
            "Approved production reference.",
            "Stable canonical view.",
            "reference-checksum",
        )
        return CanonicalResolutionResult(
            request,
            CanonicalResolutionStatus.READY,
            cap,
            (reference,),
            reference,
        )


def test_asset_enrichment_adds_canonical_graph_source_and_inventory() -> None:
    resolver = PromptGraphResolver()
    service = PromptGraphAssetEnrichmentService(
        _Assets(),  # type: ignore[arg-type]
        _Canonical(),  # type: ignore[arg-type]
        resolver,
    )

    result = service.enrich(PromptAssetEnrichmentRequest("SHT-001", ("CAP-SHP-IRON-HORIZON",)))

    assert result.ready
    assert result.canonical_asset_ids == ("CAP-SHP-IRON-HORIZON",)
    assert result.reference_ids == ("7",)
    assert result.dependencies[0].cap_checksum == "cap-checksum"
    source = result.sources[0]
    assert source.kind is PromptNodeKind.SHIP
    assert "145 metre Guild survey spacecraft" in source.content
    assert "four rear fusion engines" in source.content.casefold()
    assert "blue-white engine trails" in source.content
    assert source.reference_ids == ("7",)


def test_builder_receives_enriched_assets_without_losing_existing_sources() -> None:
    resolver = PromptGraphResolver()
    resolver.register(
        "SHT-001",
        (),
    )
    service = PromptGraphAssetEnrichmentService(
        _Assets(),  # type: ignore[arg-type]
        _Canonical(),  # type: ignore[arg-type]
        resolver,
    )
    service.enrich(PromptAssetEnrichmentRequest("SHT-001", ("CAP-SHP-IRON-HORIZON",)))
    graph = (
        PromptGraphBuilder(
            resolver,
            PromptGraphDiagnosticsFactory(),
        )
        .build(
            PromptGraphBuildContext(
                "GRAPH-001",
                "XORIX",
                "EP-001",
                "SCN-001",
                "SHT-001",
            )
        )
        .graph
    )

    ship = next(node for node in graph.nodes if node.kind is PromptNodeKind.SHIP)
    assert ship.canonical_asset_id == "CAP-SHP-IRON-HORIZON"
    assert ship.reference_ids == ("7",)
    assert ship.attribute("cap_version") == "2.0"
