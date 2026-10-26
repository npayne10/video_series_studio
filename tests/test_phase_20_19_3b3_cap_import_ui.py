"""Focused checks for guarded CAP import UI."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.presentation.dialogs.cap_document_import_dialog import (
    CAPDocumentImportDialog,
    parse_mapping_lines,
)


def test_explicit_mapping_requires_nonempty_unique_key_values():
    assert parse_mapping_lines("layout=Fixed wall\nmaterials=Matte steel") == {
        "layout": "Fixed wall",
        "materials": "Matte steel",
    }
    for invalid in ("", "layout", "=value", "layout=", "layout=a\nlayout=b"):
        with pytest.raises(ValueError):
            parse_mapping_lines(invalid)


def test_draft_targets_only_and_no_unprompted_mutation(qtbot):
    caps = Mock()
    caps.list.return_value = (
        SimpleNamespace(
            asset_id="CAP-LOC-001", title="Room", status=SimpleNamespace(value="draft")
        ),
        SimpleNamespace(
            asset_id="CAP-CHR-002",
            title="Approved character",
            status=SimpleNamespace(value="approved"),
        ),
    )
    dialog = CAPDocumentImportDialog(caps)
    qtbot.addWidget(dialog)
    assert dialog.target.count() == 1
    assert dialog.target.currentData() == "CAP-LOC-001"
    assert dialog.preview.isReadOnly()
    assert dialog.importer.specifications.caps is caps
    caps.update.assert_not_called()
    caps.create.assert_not_called()


def test_cancel_leaves_cap_untouched(qtbot):
    caps = Mock()
    caps.list.return_value = ()
    dialog = CAPDocumentImportDialog(caps)
    qtbot.addWidget(dialog)
    dialog.reject()
    assert dialog.result() == dialog.DialogCode.Rejected
    caps.update.assert_not_called()
    caps.create.assert_not_called()
