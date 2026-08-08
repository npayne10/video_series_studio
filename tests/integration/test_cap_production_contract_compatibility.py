"""Integration boundary tests for legacy CAP and the new production contract."""

from pathlib import Path

from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalAssetProfile,
    CanonicalIdentity,
    CanonicalProductionContract,
    CanonicalReferenceFamily,
    CanonicalReferenceLifecycle,
    CanonicalReferenceOrigin,
    CanonicalReferenceView,
    CAPStatus,
    ProductionAssetProjection,
    ProductionReference,
)


def test_legacy_cap_and_new_production_contract_can_coexist_during_migration() -> None:
    legacy = CanonicalAssetProfile(
        id=4,
        asset_id="CAP-SHP-004",
        title="CAP-SHP-004 — Guild Tug Ship",
        version="1.0",
        status=CAPStatus.DRAFT,
        canonical_description="A Guild tug ship.",
        visual_identity="Approved MASTER defines the visual identity.",
        production_notes="Legacy field retained until migration.",
        reference_paths=(Path("Canonical Assets/CAP-SHP-004/Images/master.png"),),
    )
    master = ProductionReference(
        reference_id="CAP-SHP-004-REF-MASTER",
        family=CanonicalReferenceFamily.MASTER,
        view=CanonicalReferenceView.MASTER,
        origin=CanonicalReferenceOrigin.CHATGPT_MASTER,
        lifecycle=CanonicalReferenceLifecycle.LOCKED,
        file_path="Canonical Assets/CAP-SHP-004/Images/master.png",
    )
    contract = CanonicalProductionContract(
        identity=CanonicalIdentity(
            asset_id=legacy.asset_id,
            canonical_name="Guild Tug Ship",
            category=AssetCategory.SHIP,
            version=legacy.version,
        ),
        canonical_description=legacy.canonical_description,
        visual_identity=legacy.visual_identity,
        production_guidance="Derived references must preserve the approved MASTER.",
        references=(master,),
    )

    projection = ProductionAssetProjection.from_contract(contract)

    assert legacy.reference_paths
    assert projection.identity.asset_id == legacy.asset_id
    assert projection.references == (master,)
    assert not hasattr(projection, "reference_paths")
