"""Unit/integration-style service coverage for structured CAP migration proposals."""

import json
from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.caps import CAPService, CAPStructuredKnowledgeService
from vscs.application.caps.design_completion import DESIGN_REVIEW_KEY
from vscs.application.caps.structured_specification import (
    SPECIFICATION_METADATA_KEY,
    CAPStructuredSpecification,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate, CAPUpdate, KnowledgeAuthority
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


def test_reviewed_cap_offline_completion_uses_only_current_accepted_fields(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    assets.create(AssetCreate(asset_id="CAP-PRP-778", name="Console", category=AssetCategory.PROP))
    caps.create(CAPCreate(asset_id="CAP-PRP-778", title="Console", canonical_description="Console"))
    spec = CAPStructuredSpecification(
        asset_id="CAP-PRP-778",
        category=AssetCategory.PROP,
        design_intent="A console",
        canonical_attributes={
            "geometry": "A tall housing with a blue display and three buttons",
        },
        master_prompt="Keep original housing",
        continuity_rules=("Keep controls in their original positions",),
    )
    audit = {
        # Save rebuilds the reviewed MASTER prompt after generating this hash.
        # Legitimate persisted reviews therefore have a different result hash.
        "result_fingerprint": "a" * 64,
        "version": 1,
        "reviewer": "Operator",
        "base_fingerprint": "b" * 64,
        "image_authorized": False,
        "fields": [
            {
                "field": "geometry",
                "decision": "accept",
                "final_value": spec.canonical_attributes["geometry"],
                "origin": "design_proposal",
            },
            {
                "field": "components",
                "decision": "defer",
                "final_value": "",
                "origin": "design_proposal",
            },
        ],
        "canon_approved": False,
    }
    caps.update(
        "CAP-PRP-778",
        CAPUpdate(
            production_metadata={
                SPECIFICATION_METADATA_KEY: spec.model_dump_json(),
                DESIGN_REVIEW_KEY: json.dumps(audit),
                "existing_review": "must stay",
            }
        ),
    )

    class NoProviderCalls(TemplateCAPGenerationProvider):
        def generate_cap(self, request):
            raise AssertionError("Offline completion must never call AI")

    service = CAPStructuredKnowledgeService(caps, NoProviderCalls())
    proposal = service.propose_from_reviewed_cap("CAP-PRP-778")
    assert {fact.key for fact in proposal.knowledge.facts} == {"geometry"}
    assert all(fact.authority is KnowledgeAuthority.PROPOSED for fact in proposal.knowledge.facts)
    assert "three buttons" in proposal.knowledge.facts[0].value
    assert proposal.knowledge.functional_identity
    assert proposal.knowledge.constraints
    assert caps.get("CAP-PRP-778").facts == ()
    assert caps.get("CAP-PRP-778").production_metadata["existing_review"] == "must stay"

    caps.update("CAP-PRP-778", CAPUpdate(canonical_description="Changed prose"))
    # An altered accepted canonical attribute fails closed even if its hash is
    # already different from the saved result hash after MASTER reconstruction.
    changed_spec = spec.model_copy(update={"canonical_attributes": {"geometry": "Changed"}})
    caps.update(
        "CAP-PRP-778",
        CAPUpdate(
            production_metadata={
                SPECIFICATION_METADATA_KEY: changed_spec.model_dump_json(),
                DESIGN_REVIEW_KEY: json.dumps(audit),
            }
        ),
    )
    from pytest import raises

    with raises(Exception, match="Reviewed field geometry does not match"):
        service.propose_from_reviewed_cap("CAP-PRP-778")
    # Unreviewed attributes must not be quietly omitted from an offline proposal.
    extra_spec = spec.model_copy(
        update={"canonical_attributes": {**spec.canonical_attributes, "materials": "Steel"}}
    )
    caps.update(
        "CAP-PRP-778",
        CAPUpdate(
            production_metadata={
                SPECIFICATION_METADATA_KEY: extra_spec.model_dump_json(),
                DESIGN_REVIEW_KEY: json.dumps(audit),
            }
        ),
    )
    with raises(Exception, match="reviewed canonical attributes"):
        service.propose_from_reviewed_cap("CAP-PRP-778")
    context.shutdown()
