"""UI contract coverage for Phase 18.2.11.2.5 and 18.2.11.2.5a."""

from pathlib import Path
from threading import Event
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QInputDialog, QMessageBox

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
    GeneratedDerivedReference,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CanonicalReferenceView
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider
from vscs.presentation.widgets.cap_derived_reference_generation import (
    DerivedReferenceGenerationDialog,
    GpuQualificationAuthorizationDialog,
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


def test_gpu_authorization_phrase_is_copyable_but_not_automatically_confirmed(qtbot) -> None:
    phrase = "AUTHORIZE GPU QUALIFICATION " + "a" * 32
    dialog = GpuQualificationAuthorizationDialog(CanonicalReferenceView.FRONT, phrase, None)
    qtbot.addWidget(dialog)
    assert dialog.phrase_field.text() == phrase
    assert dialog.phrase_field.isReadOnly()
    assert not dialog.confirm_button.isEnabled()
    dialog.copy_button.click()
    assert QApplication.clipboard().text() == phrase
    assert not dialog.confirm_button.isEnabled()
    dialog.confirmation_field.setText(phrase[:-1])
    assert not dialog.confirm_button.isEnabled()
    dialog.confirmation_field.setText(phrase)
    assert dialog.confirm_button.isEnabled()
    dialog.confirm_button.click()
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_dialog_exposes_selectable_views_and_provider(qtbot, tmp_path: Path) -> None:
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
            asset_id="CAP-SHP-905",
            name="UI Tug",
            category=AssetCategory.SHIP,
        ),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )
    registry = DerivedReferenceGeneratorRegistry()
    provider = OfflineDerivedReferencePreviewProvider()
    registry.register(provider)
    service = DerivedReferenceGenerationService(references, library, registry)

    dialog = DerivedReferenceGenerationDialog("CAP-SHP-905", service)
    qtbot.addWidget(dialog)

    assert CanonicalReferenceView.MASTER not in dialog.checkboxes
    assert CanonicalReferenceView.FRONT in dialog.checkboxes
    assert CanonicalReferenceView.TOP in dialog.checkboxes
    assert dialog.provider.currentText() == provider.name
    assert dialog.qualify_button.objectName() == "qualifyMultipleAngleView"
    assert dialog.qualify_button.isEnabled()
    assert not (project / ".vscs" / "runtime").exists()
    dialog.checkboxes[CanonicalReferenceView.FRONT].setChecked(True)
    with patch.object(QInputDialog, "getText", return_value=("", False)):
        dialog._qualify_one_view()
    assert dialog._worker is None
    assert not (project / ".vscs" / "runtime").exists()
    context.shutdown()


def test_main_window_installs_comfyui_production_provider(qtbot, tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    window = context.create_main_window()
    qtbot.addWidget(window)

    assert window.derived_reference_button is not None
    assert window.derived_reference_button.text() == "Generate Production References"
    assert not window.derived_reference_button.isEnabled()
    providers = window.cap_manager.derived_reference_service.providers.names()
    assert "ComfyUI — Qwen Derived Reference v2.1" in providers
    assert "VSCS Offline Derived Preview" in providers
    context.shutdown()


def test_generation_runs_off_gui_thread_and_blocks_duplicate_submission(qtbot, tmp_path: Path):
    context = build_application_context(_options(tmp_path))
    projects = context.services.require(ProjectService)
    project = tmp_path / "Production"
    projects.create(project, name="Production")
    (project / "master.png").write_bytes(b"master")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(asset_id="CAP-PRP-906", name="QC Console", category=AssetCategory.PROP),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )

    class BlockingProvider:
        name = "Blocking test provider"
        production_capable = False

        def __init__(self):
            self.entered = Event()
            self.release = Event()
            self.calls = 0

        def generate(self, request):
            self.calls += 1
            self.entered.set()
            assert self.release.wait(timeout=5)
            return GeneratedDerivedReference(
                filename="front.svg",
                content=b"synthetic",
                media_type="image/svg+xml",
                provider_name=self.name,
            )

    provider = BlockingProvider()
    registry = DerivedReferenceGeneratorRegistry()
    registry.register(provider)
    service = DerivedReferenceGenerationService(references, library, registry)
    dialog = DerivedReferenceGenerationDialog("CAP-PRP-906", service)
    qtbot.addWidget(dialog)
    dialog.checkboxes[CanonicalReferenceView.FRONT].setChecked(True)
    with patch.object(QMessageBox, "information"):
        dialog._generate()
        try:
            qtbot.waitUntil(provider.entered.is_set, timeout=3000)
            assert not dialog.generate_selected_button.isEnabled()
            dialog._generate()  # Never submit the same view twice while the job is live.
            assert provider.calls == 1
            assert dialog.progress_bar.maximum() == 0
        finally:
            provider.release.set()
        qtbot.waitUntil(
            lambda: dialog._worker is not None and not dialog._worker.isRunning(), timeout=5000
        )
        qtbot.waitUntil(lambda: dialog.result() == dialog.DialogCode.Accepted, timeout=3000)
    assert provider.calls == 1
    context.shutdown()
