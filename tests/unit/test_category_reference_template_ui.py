"""UI contract coverage for Phase 18.2.11.2.6 category reference templates."""

from pathlib import Path

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CanonicalReferenceView
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider
from vscs.presentation.widgets.cap_derived_reference_generation import (
    DerivedReferenceGenerationDialog,
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


def test_dialog_labels_category_requirements_and_missing_action(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    master = project / "master.png"
    master.write_bytes(b"master")

    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-SHP-931",
            name="UI Template Ship",
            category=AssetCategory.SHIP,
        ),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(OfflineDerivedReferencePreviewProvider())
    service = DerivedReferenceGenerationService(references, library, registry)

    dialog = DerivedReferenceGenerationDialog("CAP-SHP-931", service)
    qtbot.addWidget(dialog)

    assert "Category: Ship" in dialog.coverage_label.text()
    assert CanonicalReferenceView.MASTER not in dialog.checkboxes
    assert "Required" in dialog.checkboxes[CanonicalReferenceView.TOP].text()
    assert "Recommended" in dialog.checkboxes[CanonicalReferenceView.DETAIL].text()
    assert "Optional" in dialog.checkboxes[CanonicalReferenceView.INTERIOR].text()
    assert dialog.generate_missing_button.text() == "Generate Missing Required Views"
    assert dialog.generate_missing_button.isEnabled()
    context.shutdown()
