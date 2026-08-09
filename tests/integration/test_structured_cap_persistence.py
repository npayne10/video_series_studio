"""Integration coverage for Phase 19.1 structured CAP persistence."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.caps import CAPReadinessService, CAPService, ProductionProjectionService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import (
    CanonicalConstraintKind,
    CAPCreate,
    CAPStatus,
    KnowledgeAuthority,
    PersistedCanonicalConstraint,
    PersistedCanonicalFact,
    PersistedFunctionalCapability,
)


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def test_structured_cap_round_trips_and_is_published(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    projection_service = context.services.require(ProductionProjectionService)

    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-777",
            name="Persistence Ship",
            category=AssetCategory.SHIP,
            description="Structured CAP persistence acceptance asset.",
            tags=("ship", "survey"),
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-SHP-777",
            title="Persistence Ship",
            status=CAPStatus.APPROVED,
            canonical_description="A canonical survey vessel.",
            visual_identity="Stable hull geometry and markings.",
            production_notes="Preserve the approved production identity.",
            facts=(
                PersistedCanonicalFact(
                    key="class",
                    value="Survey Vessel",
                    source="Acceptance test",
                    authority=KnowledgeAuthority.CANONICAL,
                ),
            ),
            functional_identity=(
                PersistedFunctionalCapability(
                    capability="Orbital flight",
                    description="May operate in orbit.",
                    source="Acceptance test",
                    authority=KnowledgeAuthority.APPROVED,
                ),
            ),
            constraints=(
                PersistedCanonicalConstraint(
                    kind=CanonicalConstraintKind.FORBIDDEN,
                    rule="Do not alter hull markings",
                    source="Acceptance test",
                    authority=KnowledgeAuthority.APPROVED,
                ),
            ),
            semantic_tags=("ship", "survey"),
            production_classifications=("hero_asset",),
            behaviour_references=("ship.flight",),
            production_metadata={"department": "vehicles"},
        )
    )

    restored = caps.get("CAP-SHP-777")
    assert restored.facts[0].value == "Survey Vessel"
    assert restored.functional_identity[0].capability == "Orbital flight"
    assert restored.constraints[0].rule == "Do not alter hull markings"
    assert restored.semantic_tags == ("ship", "survey")
    assert restored.production_metadata == {"department": "vehicles"}

    projection = projection_service.project("CAP-SHP-777")
    assert projection.facts[0].value == "Survey Vessel"
    assert projection.functional_identity[0].capability == "Orbital flight"
    assert projection.constraints[0].rule == "Do not alter hull markings"
    assert projection.semantic_tags == ("ship", "survey")
    assert projection.production_classifications == ("hero_asset",)
    assert projection.behaviour_references == ("ship.flight",)
    assert projection.production_metadata == {"department": "vehicles"}

    context.shutdown()


def test_proposed_knowledge_does_not_satisfy_readiness_or_projection(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    readiness = context.services.require(ProductionProjectionService).readiness
    projection_service = context.services.require(ProductionProjectionService)

    assets.create(
        AssetCreate(
            asset_id="CAP-TEC-777",
            name="Proposed Technology",
            category=AssetCategory.TECHNOLOGY,
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-TEC-777",
            title="Proposed Technology",
            status=CAPStatus.APPROVED,
            canonical_description="A canonical technology asset.",
            visual_identity="Stable visual identity.",
            production_notes="Production guidance.",
            functional_identity=(
                PersistedFunctionalCapability(
                    capability="Activate",
                    authority=KnowledgeAuthority.PROPOSED,
                ),
            ),
            constraints=(
                PersistedCanonicalConstraint(
                    kind=CanonicalConstraintKind.REQUIRED,
                    rule="Preserve dimensions",
                    authority=KnowledgeAuthority.PROPOSED,
                ),
            ),
        )
    )

    report = readiness.evaluate("CAP-TEC-777")
    blocker_codes = {gap.code for gap in report.blocking_gaps}
    assert "production.functional_identity" in blocker_codes
    assert "production.constraints" in blocker_codes

    projection = projection_service.project("CAP-TEC-777")
    assert projection.functional_identity == ()
    assert projection.constraints == ()
    context.shutdown()
