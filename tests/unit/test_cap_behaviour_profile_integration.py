from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.assets import AssetService
from vscs.application.behaviours import BehaviourProfileService, ensure_behaviour_profile_service
from vscs.application.caps import (
    BehaviourProfileIncompatibleError,
    BehaviourProfileUnavailableError,
    CAPBehaviourIntegrationService,
    CAPService,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.behaviours import BehaviourAuthority, BehaviourCategory, BehaviourProfile
from vscs.domain.caps import CAPCreate


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


@pytest.fixture
def integration(tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    behaviours = ensure_behaviour_profile_service(context.services)
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-001",
            name="Survey Ship",
            category=AssetCategory.SHIP,
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-SHP-001",
            title="Survey Ship",
            canonical_description="Canonical survey ship.",
        )
    )
    service = CAPBehaviourIntegrationService(caps, behaviours)
    yield service, behaviours
    context.shutdown()


def _profile(
    profile_id: str,
    *,
    asset_category: AssetCategory = AssetCategory.SHIP,
    version: str = "1.0",
) -> BehaviourProfile:
    return BehaviourProfile(
        profile_id=profile_id,
        name=profile_id.removeprefix("BEP-").replace("-", " ").title(),
        version=version,
        category=BehaviourCategory.MANEUVERING,
        action="maneuver",
        applicable_asset_categories=(asset_category,),
    )


def _approve(behaviours: BehaviourProfileService, profile: BehaviourProfile) -> None:
    behaviours.create(profile)
    behaviours.transition(profile.profile_id, profile.version, BehaviourAuthority.PROPOSED)
    behaviours.transition(profile.profile_id, profile.version, BehaviourAuthority.APPROVED)


def test_links_stable_identity_and_resolves_authoritative_version(integration) -> None:
    service, behaviours = integration
    _approve(behaviours, _profile("BEP-SHP-DOCK"))

    updated = service.link("CAP-SHP-001", "bep-shp-dock")

    assert updated.behaviour_references == ("BEP-SHP-DOCK",)
    resolved = service.resolve_for_cap("CAP-SHP-001")
    assert resolved[0].profile_id == "BEP-SHP-DOCK"
    assert resolved[0].version == "1.0"

    behaviours.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.CANONICAL)
    behaviours.revise("BEP-SHP-DOCK", "1.0", "2.0")
    behaviours.transition("BEP-SHP-DOCK", "2.0", BehaviourAuthority.PROPOSED)
    behaviours.transition("BEP-SHP-DOCK", "2.0", BehaviourAuthority.APPROVED)

    resolved = service.resolve_for_cap("CAP-SHP-001")
    assert resolved[0].version == "1.0"
    assert resolved[0].authority is BehaviourAuthority.CANONICAL


def test_rejects_link_without_production_authority(integration) -> None:
    service, behaviours = integration
    behaviours.create(_profile("BEP-SHP-DRAFT"))

    with pytest.raises(BehaviourProfileUnavailableError):
        service.link("CAP-SHP-001", "BEP-SHP-DRAFT")


def test_rejects_incompatible_asset_category(integration) -> None:
    service, behaviours = integration
    _approve(
        behaviours,
        _profile("BEP-CHR-WALK", asset_category=AssetCategory.CHARACTER),
    )

    with pytest.raises(BehaviourProfileIncompatibleError):
        service.link("CAP-SHP-001", "BEP-CHR-WALK")


def test_available_profiles_are_production_authoritative_and_compatible(integration) -> None:
    service, behaviours = integration
    _approve(behaviours, _profile("BEP-SHP-DOCK"))
    behaviours.create(_profile("BEP-SHP-DRAFT"))
    _approve(
        behaviours,
        _profile("BEP-CHR-WALK", asset_category=AssetCategory.CHARACTER),
    )

    available = service.available_for_cap("CAP-SHP-001")

    assert tuple(profile.profile_id for profile in available) == ("BEP-SHP-DOCK",)


def test_set_behaviours_deduplicates_and_unlink_persists(integration) -> None:
    service, behaviours = integration
    _approve(behaviours, _profile("BEP-SHP-DOCK"))
    _approve(behaviours, _profile("BEP-SHP-LAND"))

    updated = service.set_behaviours(
        "CAP-SHP-001",
        ("BEP-SHP-DOCK", "BEP-SHP-LAND", "BEP-SHP-DOCK"),
    )
    assert updated.behaviour_references == ("BEP-SHP-DOCK", "BEP-SHP-LAND")

    updated = service.unlink("CAP-SHP-001", "BEP-SHP-DOCK")
    assert updated.behaviour_references == ("BEP-SHP-LAND",)
