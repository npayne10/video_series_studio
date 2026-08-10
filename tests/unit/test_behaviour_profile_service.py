from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.behaviours import (
    BehaviourGovernanceError,
    BehaviourProfileRepository,
    BehaviourProfileService,
)
from vscs.domain.assets import AssetCategory
from vscs.domain.behaviours import (
    BehaviourAuthority,
    BehaviourCategory,
    BehaviourProfile,
)
from vscs.infrastructure.database import DatabaseManager


def _profile(*, version: str = "1.0", name: str = "Dock") -> BehaviourProfile:
    return BehaviourProfile(
        profile_id="BEP-SHP-DOCK",
        version=version,
        name=name,
        category=BehaviourCategory.MANEUVERING,
        action="dock",
        applicable_asset_categories=(AssetCategory.SHIP,),
    )


@pytest.fixture
def service(tmp_path: Path) -> BehaviourProfileService:
    database = DatabaseManager()
    database.open(tmp_path / "project.db")
    return BehaviourProfileService(BehaviourProfileRepository(database))


def test_new_profiles_must_enter_as_draft(service: BehaviourProfileService) -> None:
    approved = _profile().model_copy(update={"authority": BehaviourAuthority.APPROVED})

    with pytest.raises(BehaviourGovernanceError, match="must enter governance as draft"):
        service.create(approved)


def test_governance_transitions_are_explicit_and_ordered(
    service: BehaviourProfileService,
) -> None:
    service.create(_profile())

    proposed = service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)
    approved = service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.APPROVED)
    canonical = service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.CANONICAL)

    assert proposed.authority is BehaviourAuthority.PROPOSED
    assert approved.authority is BehaviourAuthority.APPROVED
    assert canonical.authority is BehaviourAuthority.CANONICAL
    with pytest.raises(BehaviourGovernanceError, match="cannot transition"):
        service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.DRAFT)


def test_proposed_profile_can_be_returned_to_draft(service: BehaviourProfileService) -> None:
    service.create(_profile())
    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)

    draft = service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.DRAFT)

    assert draft.authority is BehaviourAuthority.DRAFT


def test_only_drafts_can_be_edited_or_deleted(service: BehaviourProfileService) -> None:
    created = service.create(_profile())
    edited = service.update_draft(created.model_copy(update={"name": "Precision Dock"}))
    assert edited.name == "Precision Dock"

    service.transition(created.profile_id, created.version, BehaviourAuthority.PROPOSED)
    with pytest.raises(BehaviourGovernanceError, match="Only draft"):
        service.update_draft(edited.model_copy(update={"name": "Changed"}))
    with pytest.raises(BehaviourGovernanceError, match="Only draft"):
        service.delete_draft(created.profile_id, created.version)


def test_revision_preserves_history_and_returns_to_draft(
    service: BehaviourProfileService,
) -> None:
    service.create(_profile())
    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)
    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.APPROVED)

    revision = service.revise("BEP-SHP-DOCK", "1.0", "2.0")

    assert revision.version == "2.0"
    assert revision.authority is BehaviourAuthority.DRAFT
    assert service.get("BEP-SHP-DOCK", "1.0").authority is BehaviourAuthority.APPROVED


def test_production_resolution_prefers_canonical_then_highest_version(
    service: BehaviourProfileService,
) -> None:
    service.create(_profile(version="1.0"))
    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)
    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.APPROVED)
    service.create(_profile(version="2.0"))
    service.transition("BEP-SHP-DOCK", "2.0", BehaviourAuthority.PROPOSED)
    service.transition("BEP-SHP-DOCK", "2.0", BehaviourAuthority.APPROVED)

    assert service.production_profile("BEP-SHP-DOCK").version == "2.0"  # type: ignore[union-attr]

    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.CANONICAL)
    resolved = service.production_profile("BEP-SHP-DOCK")
    assert resolved is not None
    assert resolved.version == "1.0"
    assert resolved.authority is BehaviourAuthority.CANONICAL


def test_draft_and_proposed_profiles_are_not_production_authority(
    service: BehaviourProfileService,
) -> None:
    service.create(_profile())
    assert service.production_profile("BEP-SHP-DOCK") is None

    service.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)
    assert service.production_profile("BEP-SHP-DOCK") is None
