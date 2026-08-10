from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

from vscs.application.assets import AssetService
from vscs.application.behaviours import ensure_behaviour_profile_service
from vscs.application.caps import CAPBehaviourIntegrationService, CAPService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.behaviours import BehaviourAuthority, BehaviourCategory, BehaviourProfile
from vscs.domain.caps import CAPCreate
from vscs.presentation.widgets.cap_behaviour_profiles import CAPBehaviourProfilesDialog


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


def test_cap_workspace_exposes_governed_behaviour_linkage(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Production", name="Production")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    behaviours = ensure_behaviour_profile_service(context.services)
    assets.create(
        AssetCreate(
            asset_id="CAP-SHP-UI",
            name="UI Ship",
            category=AssetCategory.SHIP,
        )
    )
    caps.create(
        CAPCreate(
            asset_id="CAP-SHP-UI",
            title="UI Ship",
            canonical_description="Canonical UI ship.",
        )
    )
    behaviours.create(
        BehaviourProfile(
            profile_id="BEP-SHP-DOCK",
            name="Ship Docking",
            category=BehaviourCategory.MANEUVERING,
            action="dock",
            applicable_asset_categories=(AssetCategory.SHIP,),
        )
    )
    behaviours.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.PROPOSED)
    behaviours.transition("BEP-SHP-DOCK", "1.0", BehaviourAuthority.APPROVED)

    window = context.create_main_window()
    qtbot.addWidget(window)
    window.cap_manager.refresh()
    window.cap_manager.table.selectRow(0)

    assert window.cap_behaviour_profiles_button.objectName() == "capBehaviourProfilesButton"
    assert window.cap_behaviour_profiles_button.isEnabled()
    integration = context.services.require(CAPBehaviourIntegrationService)
    dialog = CAPBehaviourProfilesDialog(integration, "CAP-SHP-UI", window.cap_manager)
    qtbot.addWidget(dialog)

    assert dialog.minimumWidth() <= 680
    assert dialog.minimumHeight() <= 480
    assert dialog.profiles.count() == 1
    item = dialog.profiles.item(0)
    assert item.data(Qt.ItemDataRole.UserRole) == "BEP-SHP-DOCK"
    item.setCheckState(Qt.CheckState.Checked)
    dialog._save()

    assert caps.get("CAP-SHP-UI").behaviour_references == ("BEP-SHP-DOCK",)
    context.shutdown()
