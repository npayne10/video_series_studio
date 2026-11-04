"""Responsive two-column CAP Production Contract editor layout."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from vscs.presentation.widgets.cap_ui_refactoring import arrange_cap_contract_columns


def test_asset_info_left_gallery_right_and_buttons_preserved(qtbot):
    dialog = QDialog()
    qtbot.addWidget(dialog)
    outer = QVBoxLayout(dialog)
    guidance = QLabel("Production Contract")
    outer.addWidget(guidance)
    scroll = QScrollArea()
    scroll.setObjectName("capEditorScrollArea")
    scroll.setWidgetResizable(True)
    scroll.setWidget(QWidget())
    outer.addWidget(scroll, 1)
    gallery = QWidget()
    gallery.setObjectName("referenceGallery")
    dialog.reference_gallery = gallery
    outer.addWidget(gallery, 1)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    outer.addWidget(buttons)

    columns = arrange_cap_contract_columns(dialog)
    assert isinstance(columns, QSplitter)
    assert columns.objectName() == "capProductionContractColumns"
    assert columns.orientation() == Qt.Orientation.Horizontal
    assert columns.widget(0) is scroll
    assert columns.widget(1) is gallery
    assert not columns.childrenCollapsible()
    assert outer.itemAt(0).widget() is guidance
    assert outer.itemAt(1).widget() is columns
    assert outer.itemAt(2).widget() is buttons


def test_two_column_arrangement_is_safe_without_gallery(qtbot):
    dialog = QDialog()
    qtbot.addWidget(dialog)
    layout = QVBoxLayout(dialog)
    scroll = QScrollArea()
    scroll.setObjectName("capEditorScrollArea")
    layout.addWidget(scroll)
    assert arrange_cap_contract_columns(dialog) is None
    assert layout.itemAt(0).widget() is scroll


def test_editor_wrapper_order_creates_columns_after_scroll_area(qtbot):
    """The contract wrapper runs before structured-knowledge scroll construction."""
    from vscs.presentation.widgets.cap_structured_knowledge import (
        _make_editor_scrollable,
    )

    dialog = QDialog()
    qtbot.addWidget(dialog)
    outer = QVBoxLayout(dialog)
    outer.addWidget(QLabel("Production Contract"))
    form = QFormLayout()
    form.addRow("CAP title", QLabel("Engineering control room"))
    outer.addLayout(form)
    gallery = QWidget()
    gallery.setObjectName("referenceGallery")
    dialog.reference_gallery = gallery
    outer.addWidget(gallery)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    outer.addWidget(buttons)

    # Before structured editor initialization the scroll widget doesn't
    # exist and the two-column hook must not destroy the form.
    assert arrange_cap_contract_columns(dialog) is None
    _make_editor_scrollable(dialog)
    columns = dialog.findChild(QSplitter, "capProductionContractColumns")
    assert columns is not None
    assert columns.widget(0).objectName() == "capEditorScrollArea"
    assert columns.widget(1) is gallery
    assert outer.itemAt(1).widget() is columns
    assert outer.itemAt(2).widget() is buttons
