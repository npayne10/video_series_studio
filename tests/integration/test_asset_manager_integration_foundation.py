"""End-to-end certification for Phase 17.5 Asset Manager Integration."""

from pathlib import Path

from vscs.application.asset_resolution import (
    AssetBrowserFilter,
    AssetBrowserService,
    AssetChangePropagationService,
    AssetDependencyIndex,
    CanonicalResolutionStatus,
    PromptAssetEnrichmentRequest,
    PromptGraphAssetEnrichmentService,
    register_asset_resolution,
)
from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.projects import ProjectService
from vscs.application.prompt_graph import (
    CompiledPromptRecord,
    IncrementalCompilationHistory,
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphResolver,
)
from vscs.bootstrap import (
    ApplicationContext,
    BootstrapOptions,
    StartupMode,
    build_application_context,
)
from vscs.domain.assets import AssetCategory, AssetCreate, AssetStatus
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CAPCreate,
    CAPStatus,
    CAPUpdate,
)


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _create_ready_asset(
    application: ApplicationContext,
    project_root: Path,
    *,
    asset_id: str,
    name: str,
    category: AssetCategory,
    canonical_description: str,
    visual_identity: str,
    production_notes: str,
) -> None:
    services = application.services
    services.require(AssetService).create(
        AssetCreate(
            asset_id=asset_id,
            name=name,
            category=category,
            description=canonical_description,
            status=AssetStatus.APPROVED,
        )
    )
    services.require(CAPService).create(
        CAPCreate(
            asset_id=asset_id,
            title=name,
            version="1.0",
            status=CAPStatus.APPROVED,
            canonical_description=canonical_description,
            visual_identity=visual_identity,
            production_notes=production_notes,
        )
    )
    reference_path = project_root / "references" / f"{asset_id}.png"
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    reference_path.write_bytes(asset_id.encode("utf-8"))
    references = services.require(CanonicalReferenceService)
    created = references.create(
        asset_id,
        CanonicalReferenceCreate(
            cap_id=1,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.PRIMARY,
            title=f"{name} primary",
            file_path=reference_path,
            description="Approved production reference.",
        ),
    )
    references.approve(references.mark_candidate(created.id).id, "Neill")


def _compiled_record(item_id: str, shot_id: str) -> CompiledPromptRecord:
    record = object.__new__(CompiledPromptRecord)
    object.__setattr__(record, "item_id", item_id)
    object.__setattr__(record, "shot_id", shot_id)
    return record


def test_asset_manager_foundation_resolves_enriches_and_propagates(
    tmp_path: Path,
) -> None:
    application = build_application_context(_options(tmp_path))
    try:
        project_root = tmp_path / "Demo"
        application.services.require(ProjectService).create(
            project_root,
            name="Demo",
        )
        _create_ready_asset(
            application,
            project_root,
            asset_id="SHP-IRON-HORIZON",
            name="Iron Horizon",
            category=AssetCategory.SHIP,
            canonical_description="A 145 metre Guild survey spacecraft.",
            visual_identity="Four rear fusion engines.",
            production_notes="Controlled blue-white engine trails.",
        )
        _create_ready_asset(
            application,
            project_root,
            asset_id="CHR-JAMES",
            name="Commander James Spence",
            category=AssetCategory.CHARACTER,
            canonical_description="A disciplined Guild commander.",
            visual_identity="Consistent approved uniform and facial identity.",
            production_notes="Preserve age, build, rank and uniform continuity.",
        )
        register_asset_resolution(application.services)

        browser = application.services.require(AssetBrowserService)
        browser_result = browser.browse(
            AssetBrowserFilter(
                require_cap=True,
                require_approved_references=True,
            )
        )
        assert tuple(item.asset_id for item in browser_result.items) == (
            "CHR-JAMES",
            "SHP-IRON-HORIZON",
        )
        assert all(
            item.canonical is not None
            and item.canonical.status is CanonicalResolutionStatus.READY
            and item.primary_reference_id is not None
            for item in browser_result.items
        )

        enrichment = application.services.require(PromptGraphAssetEnrichmentService)
        ship_result = enrichment.enrich(
            PromptAssetEnrichmentRequest(
                "EP-001-SCN-001-SHT-001",
                ("SHP-IRON-HORIZON",),
            )
        )
        character_result = enrichment.enrich(
            PromptAssetEnrichmentRequest(
                "EP-001-SCN-001-SHT-002",
                ("CHR-JAMES",),
            )
        )
        index = application.services.require(AssetDependencyIndex)
        propagation = application.services.require(AssetChangePropagationService)
        propagation.track(ship_result)
        propagation.track(character_result)

        graph = (
            application.services.require(PromptGraphBuilder)
            .build(
                PromptGraphBuildContext(
                    graph_id="GRAPH-SHIP",
                    production_id="DEMO",
                    container_id="EP-001",
                    scene_id="EP-001-SCN-001",
                    shot_id="EP-001-SCN-001-SHT-001",
                )
            )
            .graph
        )
        ship_node = graph.require_node("asset:SHP-IRON-HORIZON")
        assert "145 metre Guild survey spacecraft" in ship_node.content
        assert "Four rear fusion engines" in ship_node.content
        assert "blue-white engine trails" in ship_node.content
        assert ship_node.reference_ids
        assert index.affected_shots("SHP-IRON-HORIZON") == ("EP-001-SCN-001-SHT-001",)

        history = application.services.require(IncrementalCompilationHistory)
        history.register(_compiled_record("ITEM-SHIP", "EP-001-SCN-001-SHT-001"))
        history.register(_compiled_record("ITEM-CHARACTER", "EP-001-SCN-001-SHT-002"))
        application.services.require(CAPService).update(
            "SHP-IRON-HORIZON",
            CAPUpdate(
                version="1.1",
                production_notes=("Controlled blue-white engine trails with no orange flame."),
            ),
        )

        report = propagation.propagate("SHP-IRON-HORIZON")

        assert report.affected_shot_ids == ("EP-001-SCN-001-SHT-001",)
        assert report.refreshed_shot_ids == ("EP-001-SCN-001-SHT-001",)
        assert report.invalidated_item_ids == ("ITEM-SHIP",)
        assert history.is_invalidated("ITEM-SHIP")
        assert not history.is_invalidated("ITEM-CHARACTER")
        assert report.changes[0].asset_id == "SHP-IRON-HORIZON"
        refreshed_source = application.services.require(PromptGraphResolver).resolve(
            PromptGraphBuildContext(
                graph_id="GRAPH-SHIP-REFRESHED",
                production_id="DEMO",
                container_id="EP-001",
                scene_id="EP-001-SCN-001",
                shot_id="EP-001-SCN-001-SHT-001",
            )
        )[0]
        assert "no orange flame" in refreshed_source.content
    finally:
        application.shutdown()
