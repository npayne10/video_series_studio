"""Integration coverage for CAP and canonical-reference resolution."""

from pathlib import Path

from vscs.application.asset_resolution import (
    CanonicalResolutionRequest,
    CanonicalResolutionService,
    CanonicalResolutionStatus,
    register_asset_resolution,
)
from vscs.application.assets import AssetService
from vscs.application.caps import CanonicalReferenceService, CAPService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate, AssetStatus
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceType,
    CAPCreate,
    CAPStatus,
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


def test_project_cap_and_primary_reference_resolve_for_production(
    tmp_path: Path,
) -> None:
    application = build_application_context(_options(tmp_path))
    try:
        application.services.require(ProjectService).create(
            tmp_path / "Demo",
            name="Demo",
        )
        assets = application.services.require(AssetService)
        assets.create(
            AssetCreate(
                asset_id="CAP-SHP-IRON-HORIZON",
                name="Iron Horizon",
                category=AssetCategory.SHIP,
                description="Guild survey spacecraft.",
                status=AssetStatus.APPROVED,
            )
        )
        caps = application.services.require(CAPService)
        caps.create(
            CAPCreate(
                asset_id="CAP-SHP-IRON-HORIZON",
                title="Iron Horizon",
                version="2.0",
                status=CAPStatus.APPROVED,
                canonical_description="A 145 metre Guild survey spacecraft.",
                visual_identity="Four rear fusion engines.",
                production_notes="Controlled blue-white engine trails.",
            )
        )
        reference_path = tmp_path / "Demo" / "references" / "iron_horizon.png"
        reference_path.parent.mkdir(parents=True, exist_ok=True)
        reference_path.write_bytes(b"reference")
        references = application.services.require(CanonicalReferenceService)
        created = references.create(
            "CAP-SHP-IRON-HORIZON",
            CanonicalReferenceCreate(
                cap_id=1,
                reference_type=CanonicalReferenceType.IMAGE,
                role=CanonicalReferenceRole.PRIMARY,
                title="Iron Horizon primary",
                file_path=reference_path,
                description="Approved starboard production reference.",
            ),
        )
        candidate = references.mark_candidate(created.id)
        references.approve(candidate.id, "Neill")
        register_asset_resolution(application.services)

        result = application.services.require(CanonicalResolutionService).resolve(
            CanonicalResolutionRequest("CAP-SHP-IRON-HORIZON")
        )

        assert result.status is CanonicalResolutionStatus.READY
        assert result.cap is not None
        assert result.cap.version == "2.0"
        assert result.primary_reference is not None
        assert result.primary_reference.title == "Iron Horizon primary"
        assert result.fingerprint is not None
    finally:
        application.shutdown()
