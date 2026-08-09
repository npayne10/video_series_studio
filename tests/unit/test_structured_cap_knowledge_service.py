"""Unit/integration-style service coverage for structured CAP migration proposals."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.caps import CAPService, CAPStructuredKnowledgeService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate, KnowledgeAuthority
from vscs.infrastructure.ai import TemplateCAPGenerationProvider


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


def test_ai_proposal_is_non_mutating_until_explicitly_applied(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    projects.create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    assets.create(
        AssetCreate(
            asset_id="CAP-LOC-778",
            name="Legacy Location",
            category=AssetCategory.LOCATION,
            description="A legacy location.",
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-LOC-778",
            title="Legacy Location",
            canonical_description="A stone transit hall with two entrances.",
            visual_identity="Grey stone and brushed metal.",
            production_notes="Preserve the two entrances.",
        )
    )
    service = CAPStructuredKnowledgeService(caps, TemplateCAPGenerationProvider())

    proposal = service.propose("CAP-LOC-778")
    assert proposal.knowledge.facts
    assert all(fact.authority is KnowledgeAuthority.PROPOSED for fact in proposal.knowledge.facts)
    assert caps.get("CAP-LOC-778").facts == ()

    applied = service.apply("CAP-LOC-778", proposal.knowledge)
    assert all(fact.authority is KnowledgeAuthority.APPROVED for fact in applied.facts)
    assert caps.get("CAP-LOC-778").facts
    assert not service.needs_migration("CAP-LOC-778")
    context.shutdown()
