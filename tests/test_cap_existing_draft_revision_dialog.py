"""Existing Draft field-review dialog: accepted decisions remain non-editable."""

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.design_completion import (
    DesignFieldReview,
    DetailDecision,
    DetailOrigin,
)
from vscs.presentation.dialogs import edit_existing_draft_cap_dialog as ui


def _dialog(qtbot):
    fields = (
        DesignFieldReview(
            field="materials",
            proposed_value="Graphite",
            final_value="Graphite",
            decision=DetailDecision.ACCEPT,
            origin=DetailOrigin.DESIGN_PROPOSAL,
        ),
        DesignFieldReview(
            field="geometry",
            proposed_value="A blue display",
            decision=DetailDecision.DEFER,
            origin=DetailOrigin.UNRESOLVED,
        ),
    )
    snapshot = SimpleNamespace(
        story_id="STORY-001",
        asset_id="STORY-PRO-TEST",
        review=SimpleNamespace(fields=fields),
    )
    service = Mock()
    dialog = ui.EditExistingDraftCAPDialog(service, snapshot)
    qtbot.addWidget(dialog)
    return dialog, service


def test_accepted_fields_are_read_only_and_only_deferred_field_selectable(qtbot):
    dialog, _service = _dialog(qtbot)
    assert dialog.accepted_view.isReadOnly()
    assert "materials: Graphite" in dialog.accepted_view.toPlainText()
    assert dialog.field.count() == 1
    assert dialog.field.currentData() == "geometry"
    assert "blue display" in dialog.original_proposal.toPlainText()
    assert dialog.original_proposal.isReadOnly()
    assert dialog.value.isReadOnly()
    assert dialog.rationale.isReadOnly()
    assert dialog.save_button is not None and not dialog.save_button.isEnabled()


def test_cancelled_field_confirmation_makes_no_write(qtbot, monkeypatch):
    dialog, _service = _dialog(qtbot)
    save = Mock()
    monkeypatch.setattr(ui, "save_draft_cap_field_revision", save)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.No,
    )
    dialog._save()
    save.assert_not_called()


def test_manual_text_cannot_activate_save_without_generated_proposal(qtbot, monkeypatch):
    dialog, _service = _dialog(qtbot)
    save = Mock()
    monkeypatch.setattr(ui, "save_draft_cap_field_revision", save)
    monkeypatch.setattr(QMessageBox, "warning", Mock())
    dialog.value.setPlainText("Manually written rectangle")
    dialog.rationale.setPlainText("Manual explanation")
    dialog._save()
    save.assert_not_called()
    assert not dialog.save_button.isEnabled()


def test_rejection_clears_generated_proposal_and_blocks_save(qtbot):
    dialog, _service = _dialog(qtbot)
    dialog._request = Mock()
    dialog._proposal = Mock()
    dialog.value.setPlainText("AI generated rectangle")
    dialog.save_button.setEnabled(True)
    dialog.reject_button.click()
    assert dialog._proposal is None
    assert dialog._request is None
    assert not dialog.save_button.isEnabled()
    assert dialog.value.toPlainText() == ""


def _automatic_test_setup(dialog, service, monkeypatch, tmp_path):
    service.batch.generator.generator.assets.projects.project_directory = tmp_path
    service.batch.generator.generator.provider = Mock()
    request = SimpleNamespace(field="geometry")
    proposal = SimpleNamespace(
        field="geometry",
        proposed_value="AI generated rectangular console enclosure",
        rationale="A proposed form compatible with accepted components",
        source_type="AI-proposed design; not established Story canon",
        request_fingerprint="generation-sha",
    )
    cache = Mock()
    cache.next_number.return_value = 1
    cache.latest_completed_number.return_value = 1
    cache.load.return_value = proposal
    monkeypatch.setattr(ui, "DraftCAPFieldProposalCache", lambda _root: cache)
    monkeypatch.setattr(ui, "prepare_field_request", Mock(return_value=request))
    provider_call = Mock(return_value=proposal)
    monkeypatch.setattr(ui, "generate_field_proposal", provider_call)
    monkeypatch.setattr(ui, "verify_proposal_for_review", Mock())
    monkeypatch.setattr(
        ui.AutomationProgressRunner,
        "run",
        lambda _runner, _title, _story, action, *, may_charge: action(),
    )
    return cache, provider_call, request, proposal


def test_declined_paid_generation_never_reserves_or_calls_provider(
    qtbot, monkeypatch, tmp_path
):
    dialog, service = _dialog(qtbot)
    cache, provider_call, _request, _proposal = _automatic_test_setup(
        dialog, service, monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No
    )
    dialog.generate_button.click()
    cache.reserve.assert_not_called()
    provider_call.assert_not_called()
    assert not dialog.save_button.isEnabled()


def test_ai_generated_proposal_needs_separate_approval(qtbot, monkeypatch, tmp_path):
    dialog, service = _dialog(qtbot)
    cache, provider_call, request, proposal = _automatic_test_setup(
        dialog, service, monkeypatch, tmp_path
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QMessageBox, "information", Mock())
    save = Mock()
    monkeypatch.setattr(ui, "save_draft_cap_field_revision", save)
    dialog.generate_button.click()
    cache.reserve.assert_called_once_with(request)
    provider_call.assert_called_once()
    assert dialog.value.isReadOnly()
    assert dialog.value.toPlainText() == proposal.proposed_value
    assert dialog.save_button.isEnabled()
    save.assert_not_called()
    dialog._save()
    assert save.call_args.kwargs["reviewed_value"] == proposal.proposed_value
    assert "generation-sha" in save.call_args.kwargs["rationale"]
    assert save.call_args.kwargs["field"] == "geometry"


def test_reopen_cached_proposal_uses_zero_provider_calls(qtbot, monkeypatch, tmp_path):
    dialog, service = _dialog(qtbot)
    cache, provider_call, request, proposal = _automatic_test_setup(
        dialog, service, monkeypatch, tmp_path
    )
    dialog.load_cached_button.click()
    cache.load.assert_called_once_with(request)
    provider_call.assert_not_called()
    assert dialog.value.toPlainText() == proposal.proposed_value
    assert dialog.save_button.isEnabled()
