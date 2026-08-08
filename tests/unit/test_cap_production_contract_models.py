"""Unit tests for Phase 18.2.11.2.2 CAP production-contract models."""

import pytest
from pydantic import ValidationError

from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalConstraint,
    CanonicalConstraintKind,
    CanonicalFact,
    CanonicalIdentity,
    CanonicalProductionContract,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
    CAPReadiness,
    CAPReadinessState,
    FunctionalCapability,
    ProductionAssetProjection,
    ProductionReference,
)


def _master() -> ProductionReference:
    return ProductionReference(
        reference_id="CAP-SHP-004-REF-MASTER",
        family=CanonicalReferenceFamily.MASTER,
        view=CanonicalReferenceView.MASTER,
        origin=CanonicalReferenceOrigin.CHATGPT_MASTER,
        lifecycle=CanonicalReferenceLifecycle.LOCKED,
        file_path="Canonical Assets/CAP-SHP-004/Images/master.png",
    )


def _derived(view: CanonicalReferenceView) -> ProductionReference:
    return ProductionReference(
        reference_id=f"CAP-SHP-004-REF-{view.value.upper()}",
        family=CanonicalReferenceFamily.PRODUCTION_VIEW,
        view=view,
        origin=CanonicalReferenceOrigin.VSCS_DERIVED,
        lifecycle=CanonicalReferenceLifecycle.APPROVED,
        parent_reference_id="CAP-SHP-004-REF-MASTER",
        file_path=f"Canonical Assets/CAP-SHP-004/Images/{view.value}.png",
        generator="test-provider",
    )


def _contract(*references: ProductionReference) -> CanonicalProductionContract:
    return CanonicalProductionContract(
        identity=CanonicalIdentity(
            asset_id="cap-shp-004",
            canonical_name="Guild Tug Ship",
            category=AssetCategory.SHIP,
            aliases=("Tug", "Tug"),
            version="1.0",
        ),
        canonical_description="A Guild tug ship used for controlled spacecraft towing.",
        facts=(CanonicalFact(key="purpose", value="spacecraft towing"),),
        visual_identity="Preserve the approved MASTER hull identity and proportions.",
        functional_identity=(
            FunctionalCapability(
                capability="towing",
                description="Can tow compatible spacecraft under controlled operations.",
            ),
        ),
        constraints=(
            CanonicalConstraint(
                kind=CanonicalConstraintKind.FORBIDDEN,
                rule="Do not invent weapons unless later canon explicitly approves them.",
            ),
        ),
        production_guidance="Use approved viewpoint references appropriate to the planned camera.",
        references=references,
        readiness=CAPReadiness(
            identity=CAPReadinessState.READY,
            references=CAPReadinessState.READY,
            generation=CAPReadinessState.READY,
            production=CAPReadinessState.READY,
            canonical_locked=True,
        ),
    )


def test_contract_requires_exactly_one_chatgpt_master_reference() -> None:
    master = _master()

    contract = _contract(master)

    assert contract.identity.asset_id == "CAP-SHP-004"
    assert contract.identity.aliases == ("Tug",)
    assert contract.references == (master,)

    with pytest.raises(ValidationError, match="exactly one MASTER"):
        _contract()

    with pytest.raises(ValidationError, match="exactly one MASTER"):
        _contract(master, master.model_copy(update={"reference_id": "OTHER-MASTER"}))


def test_master_reference_cannot_be_vscs_authored_or_have_parent() -> None:
    with pytest.raises(ValidationError, match="originate from ChatGPT"):
        ProductionReference(
            reference_id="MASTER",
            family=CanonicalReferenceFamily.MASTER,
            view=CanonicalReferenceView.MASTER,
            origin=CanonicalReferenceOrigin.VSCS_DERIVED,
            file_path="master.png",
            parent_reference_id="OTHER",
        )


def test_vscs_derived_reference_requires_direct_master_traceability() -> None:
    master = _master()
    top = _derived(CanonicalReferenceView.TOP)

    contract = _contract(master, top)

    assert contract.references[1].parent_reference_id == master.reference_id
    assert contract.references[1].origin is CanonicalReferenceOrigin.VSCS_DERIVED

    wrong_parent = top.model_copy(update={"parent_reference_id": "UNKNOWN"})
    with pytest.raises(ValidationError, match="not part of this CAP"):
        _contract(master, wrong_parent)


def test_contract_rejects_duplicate_reference_ids() -> None:
    master = _master()
    first = _derived(CanonicalReferenceView.FRONT)
    second = _derived(CanonicalReferenceView.REAR).model_copy(
        update={"reference_id": first.reference_id}
    )

    with pytest.raises(ValidationError, match="reference IDs must be unique"):
        _contract(master, first, second)


def test_projection_exposes_only_approved_or_locked_references() -> None:
    master = _master()
    front = _derived(CanonicalReferenceView.FRONT)
    candidate = _derived(CanonicalReferenceView.TOP).model_copy(
        update={"lifecycle": CanonicalReferenceLifecycle.CANDIDATE}
    )
    contract = _contract(master, front, candidate)

    projection = ProductionAssetProjection.from_contract(contract)

    assert projection.identity == contract.identity
    assert {reference.reference_id for reference in projection.references} == {
        master.reference_id,
        front.reference_id,
    }
    assert candidate.reference_id not in {
        reference.reference_id for reference in projection.references
    }


def test_readiness_dimensions_are_independent() -> None:
    readiness = CAPReadiness(
        identity=CAPReadinessState.READY,
        references=CAPReadinessState.INCOMPLETE,
        generation=CAPReadinessState.BLOCKED,
        production=CAPReadinessState.READY,
        blockers=("Top production view missing",),
    )

    assert readiness.identity is CAPReadinessState.READY
    assert readiness.references is CAPReadinessState.INCOMPLETE
    assert readiness.generation is CAPReadinessState.BLOCKED
    assert readiness.production is CAPReadinessState.READY
