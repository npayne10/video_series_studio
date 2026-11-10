"""Database acceptance: Draft CAP metadata revision is atomic and stale-safe."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetService
from vscs.application.caps import CAPService
from vscs.application.caps.repository import CAPRepositoryError
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CAPCreate, CAPStatus, CAPUpdate


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


def test_atomic_draft_metadata_cas_rejects_stale_and_approved(tmp_path):
    ctx = build_application_context(_options(tmp_path))
    try:
        ctx.services.require(ProjectService).create(tmp_path / "DraftTest", name="DraftTest")
        assets = ctx.services.require(AssetService)
        caps = ctx.services.require(CAPService)
        assets.create(
            AssetCreate(
                asset_id="CAP-PRP-REVISION",
                name="Disposable console",
                category=AssetCategory.PROP,
            )
        )
        caps.create(
            CAPCreate(
                asset_id="CAP-PRP-REVISION",
                title="Disposable console",
                status=CAPStatus.DRAFT,
                canonical_description="Existing reviewed Draft",
                production_metadata={"existing": "preserve"},
            )
        )
        repo = caps.repository
        updated = repo.compare_and_swap_draft_metadata(
            "CAP-PRP-REVISION",
            expected={"existing": "preserve"},
            replacement={"existing": "preserve", "revision": "geometry reviewed"},
        )
        assert updated.status is CAPStatus.DRAFT
        assert updated.production_metadata["existing"] == "preserve"
        assert caps.get("CAP-PRP-REVISION").production_metadata["revision"] == "geometry reviewed"
        with pytest.raises(CAPRepositoryError, match="changed"):
            repo.compare_and_swap_draft_metadata(
                "CAP-PRP-REVISION",
                expected={"existing": "preserve"},
                replacement={"revision": "stale would overwrite"},
            )
        assert caps.get("CAP-PRP-REVISION").production_metadata["revision"] == "geometry reviewed"
        caps.update("CAP-PRP-REVISION", CAPUpdate(status=CAPStatus.APPROVED))
        with pytest.raises(CAPRepositoryError, match="approved"):
            repo.compare_and_swap_draft_metadata(
                "CAP-PRP-REVISION",
                expected={"existing": "preserve", "revision": "geometry reviewed"},
                replacement={"revision": "unsafe"},
            )
        assert caps.get("CAP-PRP-REVISION").status is CAPStatus.APPROVED
    finally:
        ctx.shutdown()
