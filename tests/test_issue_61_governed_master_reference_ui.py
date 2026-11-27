"""Issue #61: the visible approval route must update governed reference authority."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QMessageBox

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.caps.readiness_service import CAPReadinessService
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import (
    CanonicalReferenceLifecycle,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceUpdate,
    CanonicalReferenceView,
)
from vscs.infrastructure.ai.derived_reference_provider import OfflineDerivedReferencePreviewProvider
from vscs.presentation.widgets.asset_manager import AssetEditDialog
from vscs.presentation.widgets.canonical_reference_gallery import CanonicalReferenceGallery
from vscs.presentation.widgets.cap_derived_reference_generation import (
    DerivedReferenceGenerationDialog,
)
from vscs.presentation.widgets.cap_reference_file_management import (
    ReferenceEvidenceDialog,
    _approve,
    _archive,
    _reject,
    _set_primary_reference,
    _unlock,
)


def test_rejected_derived_candidate_retains_image_reason_and_replacement_lineage(tmp_path):
    context, project, _assets, _caps, references, library, master, generator, provider = _context(
        tmp_path
    )
    original = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.FRONT,), provider_name=provider
    )[0]
    original_path = project / references.get(original).file_path
    original_bytes = original_path.read_bytes()
    dialog = _dialog(references)
    with (
        patch(
            "vscs.presentation.widgets.cap_reference_file_management.QInputDialog.getMultiLineText",
            return_value=("Oblique, not straight-on Front", True),
        ),
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "critical") as errors,
    ):
        _reject(dialog, original)
    errors.assert_not_called()
    rejected = library.get(original)
    assert rejected.lifecycle is CanonicalReferenceLifecycle.REJECTED
    assert rejected.history[-1].note == "Oblique, not straight-on Front"

    replacement = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.FRONT,), provider_name=provider, seed=1
    )[0]
    replacement_record = references.get(replacement)
    assert replacement_record.file_path != references.get(original).file_path
    assert f"Supersedes reference: {rejected.reference_id}" in replacement_record.notes
    assert sha256(original_bytes).hexdigest() in replacement_record.notes
    assert original_path.read_bytes() == original_bytes
    assert library.get(replacement).lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    assert library.get(master.reference_record_id).lifecycle is CanonicalReferenceLifecycle.LOCKED
    context.shutdown()


def test_blank_candidate_qc_reason_does_not_mutate_authority(tmp_path):
    context, _project, _assets, _caps, references, library, _master, generator, provider = _context(
        tmp_path
    )
    candidate = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.REAR,), provider_name=provider
    )[0]
    with (
        patch(
            "vscs.presentation.widgets.cap_reference_file_management.QInputDialog.getMultiLineText",
            return_value=("   ", True),
        ),
        patch.object(QMessageBox, "warning") as warning,
    ):
        _reject(_dialog(references), candidate)
    warning.assert_called_once()
    assert library.get(candidate).lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    context.shutdown()


def _context(tmp_path: Path):
    options = BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )
    context = build_application_context(options)
    project = tmp_path / "Project"
    context.services.require(ProjectService).create(project, name="Master Review Audit")
    references = context.services.require(CanonicalReferenceService)
    caps = context.services.require(CAPService)
    assets = context.services.require(AssetService)
    library = ReferenceLibraryService(references)
    master_file = project / "references" / "console_master.png"
    master_file.parent.mkdir(parents=True)
    master_file.write_bytes(b"synthetic test authority, not a real ChatGPT image")
    master = CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(
            asset_id="CAP-PRP-999",
            name="Controlled Synthetic Console",
            category=AssetCategory.PROP,
            description="Synthetic fixture only; not production authority.",
        ),
        Path("references/console_master.png"),
        confirmed_chatgpt_master=True,
        actor="Fixture Operator",
    )
    providers = DerivedReferenceGeneratorRegistry()
    offline = OfflineDerivedReferencePreviewProvider()
    providers.register(offline)
    generator = DerivedReferenceGenerationService(references, library, providers)
    return context, project, assets, caps, references, library, master, generator, offline.name


def _dialog(references):
    return SimpleNamespace(reference_service=references, _refresh_references=Mock())


def test_derived_gallery_approval_updates_governed_library_and_readiness(tmp_path):
    context, _root, _assets, caps, references, library, master, generator, provider = _context(
        tmp_path
    )
    derived_id = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.FRONT,), provider_name=provider
    )[0]
    assert library.get(derived_id).lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    before = CAPReadinessService(caps, references, library).evaluate("CAP-PRP-999")
    assert any("Front" in gap.message for gap in before.references.gaps)

    dialog = _dialog(references)
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "critical") as errors,
    ):
        _approve(dialog, derived_id)
    errors.assert_not_called()
    dialog._refresh_references.assert_called_once()
    assert references.get(derived_id).status is CanonicalReferenceStatus.APPROVED
    assert library.get(derived_id).lifecycle is CanonicalReferenceLifecycle.APPROVED
    assert library.get(master.reference_record_id).lifecycle is CanonicalReferenceLifecycle.LOCKED

    after = CAPReadinessService(caps, references, library).evaluate("CAP-PRP-999")
    assert not any("Front" in gap.message for gap in after.references.gaps)
    assert not after.references.ready  # Rear/Left/Right remain genuinely missing.
    assert not after.production.ready  # Draft CAP remains unapproved.
    context.shutdown()


def test_rear_qualification_approval_requires_all_three_confirmations(tmp_path):
    context, _root, _assets, _caps, references, library, _master, generator, provider = _context(
        tmp_path
    )
    candidate = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.REAR,), provider_name=provider
    )[0]
    references.update(
        candidate,
        CanonicalReferenceUpdate(file_path=Path("Derived/rear_qualification_qa.png")),
    )
    dialog = _dialog(references)
    review_entries = iter(
        [
            ("PASS: Rear camera near perpendicular; a slight top face remains visible.", True),
            (
                "Reviewed actual engineering drawing revision A: rear surface has "
                "no added ports, vents, or unverified features.",
                True,
            ),
        ]
    )
    with (
        patch(
            "vscs.presentation.widgets.cap_reference_file_management._request_reference_evidence",
            side_effect=lambda *args: next(review_entries),
        ) as prompts,
        patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes
        ) as questions,
        patch.object(QMessageBox, "information") as notices,
    ):
        _approve(dialog, candidate)

    assert prompts.call_count == 2  # Camera QC and distinct geometry evidence
    assert [call.args[1] for call in questions.call_args_list] == [
        "Accept Camera Viewpoint?",
        "Verify Canonical Geometry?",
        "Approve Canonical Reference",
    ]
    notices.assert_not_called()
    assert library.get(candidate).lifecycle is CanonicalReferenceLifecycle.APPROVED
    assert "CANONICAL GEOMETRY REVIEW: VERIFIED" in library.get(candidate).history[-1].note
    context.shutdown()


def test_rear_camera_decline_explains_unchanged_candidate(tmp_path):
    context, _root, _assets, _caps, references, library, _master, generator, provider = _context(
        tmp_path
    )
    candidate = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.REAR,), provider_name=provider
    )[0]
    references.update(
        candidate,
        CanonicalReferenceUpdate(file_path=Path("Derived/rear_qualification_qa.png")),
    )
    with (
        patch(
            "vscs.presentation.widgets.cap_reference_file_management._request_reference_evidence",
            return_value=("PASS: Rear camera aligned with a small visible top face.", True),
        ),
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No),
        patch.object(QMessageBox, "information") as notices,
    ):
        _approve(_dialog(references), candidate)
    notices.assert_called_once()
    assert "Camera Viewpoint" in notices.call_args.args[1]
    assert library.get(candidate).lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    context.shutdown()


def test_reference_evidence_dialog_wraps_and_resizes(qtbot):
    instructions = (
        "Explain how newly visible panels, vents and structural features were checked. " * 8
    )
    dialog = ReferenceEvidenceDialog("Canonical Geometry Evidence Required", instructions)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.instruction_label.wordWrap()
    assert dialog.instruction_label.text() == instructions
    assert dialog.size().width() >= 780
    dialog.resize(520, 440)
    assert dialog.width() == 520
    dialog.evidence_edit.setPlainText("Approved drawing revision A, rear face verified.")
    assert "drawing revision A" in dialog.evidence_edit.toPlainText()


def test_derived_primary_and_locked_master_unlock_are_blocked(tmp_path):
    context, _root, _assets, _caps, references, library, master, generator, provider = _context(
        tmp_path
    )
    derived_id = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.LEFT,), provider_name=provider
    )[0]
    dialog = _dialog(references)
    with patch.object(QMessageBox, "critical") as errors:
        _set_primary_reference(dialog, derived_id)
    assert errors.called
    assert references.get(derived_id).role is CanonicalReferenceRole.SUPPLEMENTARY
    assert references.get(master.reference_record_id).role is CanonicalReferenceRole.PRIMARY

    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "critical") as errors,
    ):
        _unlock(dialog, master.reference_record_id)
    assert errors.called
    assert references.get(master.reference_record_id).locked
    assert library.get(master.reference_record_id).lifecycle is CanonicalReferenceLifecycle.LOCKED
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "critical") as errors,
    ):
        _archive(dialog, master.reference_record_id)
    assert errors.called
    assert references.get(master.reference_record_id).status is CanonicalReferenceStatus.APPROVED
    assert library.get(master.reference_record_id).lifecycle is CanonicalReferenceLifecycle.LOCKED
    context.shutdown()


def test_derived_gallery_archive_updates_library_as_well_as_reference(tmp_path):
    context, _root, _assets, _caps, references, library, _master, generator, provider = _context(
        tmp_path
    )
    derived_id = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.RIGHT,), provider_name=provider
    )[0]
    dialog = _dialog(references)
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "critical") as errors,
    ):
        _archive(dialog, derived_id)
    errors.assert_not_called()
    assert references.get(derived_id).status is CanonicalReferenceStatus.ARCHIVED
    assert library.get(derived_id).lifecycle is CanonicalReferenceLifecycle.ARCHIVED
    context.shutdown()


def test_asset_editor_does_not_claim_master_lock_from_registry_path(qtbot, tmp_path):
    context, project, assets, _caps, _references, library, master, _generator, _provider = _context(
        tmp_path
    )
    asset = assets.get("CAP-PRP-999")
    # A registry file path alone is not a production library MASTER.
    without_authority = AssetEditDialog(asset, project, master_lifecycle=None)
    qtbot.addWidget(without_authority)
    assert "not a locked MASTER" in without_authority.master_status.text()

    locked = AssetEditDialog(
        asset, project, master_lifecycle=library.get(master.reference_record_id).lifecycle
    )
    qtbot.addWidget(locked)
    assert locked.master_status.text() == "Locked canonical authority"

    # Selecting the same file explicitly must allow a missing MASTER attachment;
    # an unchanged text path must never constitute authority or consent by itself.
    with patch(
        "vscs.presentation.widgets.asset_manager.QFileDialog.getOpenFileName",
        return_value=(str(project / asset.file_path), "Images"),
    ):
        without_authority._browse_master()
    assert without_authority.master_changed()
    assert without_authority.master_confirmation.isEnabled()
    assert not without_authority.confirmed_chatgpt_master()
    context.shutdown()


def test_gallery_displays_governance_and_disables_derived_primary(qtbot, tmp_path):
    context, project, _assets, _caps, references, library, master, generator, provider = _context(
        tmp_path
    )
    derived_id = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.FRONT,), provider_name=provider
    )[0]
    gallery = CanonicalReferenceGallery()
    qtbot.addWidget(gallery)
    gallery.set_references(
        references.list_for_cap("CAP-PRP-999"),
        project,
        governed_entries=library.list_for_cap("CAP-PRP-999"),
    )
    for i in range(gallery.gallery.count()):
        if gallery.gallery.item(i).data(gallery.REFERENCE_ID_ROLE) == derived_id:
            gallery.gallery.setCurrentRow(i)
            break
    assert "Production View" in gallery.governance_label.text()
    assert "Candidate" in gallery.governance_label.text()
    assert not gallery.primary_button.isEnabled()
    for i in range(gallery.gallery.count()):
        if gallery.gallery.item(i).data(gallery.REFERENCE_ID_ROLE) == master.reference_record_id:
            gallery.gallery.setCurrentRow(i)
            break
    assert "Master" in gallery.governance_label.text()
    assert not gallery.archive_button.isEnabled()
    assert not gallery.unlock_button.isEnabled()
    context.shutdown()


def test_old_gallery_only_approval_can_be_explicitly_reconciled(qtbot, tmp_path):
    context, project, _assets, _caps, references, library, _master, generator, provider = _context(
        tmp_path
    )
    derived_id = generator.generate(
        "CAP-PRP-999", (CanonicalReferenceView.FRONT,), provider_name=provider
    )[0]
    references.approve(derived_id, "Old gallery before Issue 61")
    assert library.get(derived_id).lifecycle is CanonicalReferenceLifecycle.CANDIDATE
    gallery = CanonicalReferenceGallery()
    qtbot.addWidget(gallery)
    gallery.set_references(
        references.list_for_cap("CAP-PRP-999"),
        project,
        governed_entries=library.list_for_cap("CAP-PRP-999"),
    )
    for i in range(gallery.gallery.count()):
        if gallery.gallery.item(i).data(gallery.REFERENCE_ID_ROLE) == derived_id:
            gallery.gallery.setCurrentRow(i)
            break
    assert gallery.approve_button.isEnabled()  # Explicit operator reconciliation.
    with (
        patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
        patch.object(QMessageBox, "critical") as errors,
    ):
        _approve(_dialog(references), derived_id)
    errors.assert_not_called()
    assert library.get(derived_id).lifecycle is CanonicalReferenceLifecycle.APPROVED
    context.shutdown()


def test_legacy_master_unlock_cannot_satisfy_governed_master_gates(tmp_path):
    context, _root, assets, caps, references, library, master, generator, provider = _context(
        tmp_path
    )
    references.unlock(master.reference_record_id)  # Simulate pre-#61 gallery divergence.
    assert library.get(master.reference_record_id).lifecycle is CanonicalReferenceLifecycle.LOCKED
    assert references.get(master.reference_record_id).status is CanonicalReferenceStatus.CANDIDATE
    assert (
        CanonicalAssetCreationService(assets, caps, references, library).active_master_lifecycle(
            "CAP-PRP-999"
        )
        is None
    )
    report = CAPReadinessService(caps, references, library).evaluate("CAP-PRP-999")
    assert not report.identity.ready
    assert not report.references.ready
    assert not report.production.ready
    with pytest.raises(DerivedReferenceGenerationError, match="authority mismatch"):
        generator.generate("CAP-PRP-999", (CanonicalReferenceView.FRONT,), provider_name=provider)
    context.shutdown()


def test_derived_generation_dialog_shows_missing_master_as_blocker(qtbot, tmp_path):
    context, _root, _assets, _caps, references, _library, master, generator, _provider = _context(
        tmp_path
    )
    references.unlock(master.reference_record_id)
    dialog = DerivedReferenceGenerationDialog("CAP-PRP-999", generator)
    qtbot.addWidget(dialog)
    assert "BLOCKED" in dialog.master_authority_label.text()
    assert not dialog.generate_missing_button.isEnabled()
    assert not dialog.generate_selected_button.isEnabled()
    context.shutdown()
