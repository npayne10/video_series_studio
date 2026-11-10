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
