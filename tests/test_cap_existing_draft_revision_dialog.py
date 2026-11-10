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


def test_cancelled_field_confirmation_makes_no_write(qtbot, monkeypatch):
    dialog, _service = _dialog(qtbot)
    save = Mock()
    monkeypatch.setattr(ui, "save_draft_cap_field_revision", save)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.No,
    )
    dialog.value.setPlainText("Rectangular housing")
    dialog.rationale.setPlainText("Approved as disposable design proposal")
    dialog._save()
    save.assert_not_called()


def test_confirmed_revision_passes_one_field_and_rationale(qtbot, monkeypatch):
    dialog, service = _dialog(qtbot)
    save = Mock()
    monkeypatch.setattr(ui, "save_draft_cap_field_revision", save)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(QMessageBox, "information", Mock())
    dialog.value.setPlainText("Rectangular housing")
    dialog.rationale.setPlainText("Operator-approved Draft design choice")
    dialog._save()
    save.assert_called_once_with(
        service,
        dialog.snapshot,
        field="geometry",
        reviewed_value="Rectangular housing",
        rationale="Operator-approved Draft design choice",
        reviewer="Operator",
    )
