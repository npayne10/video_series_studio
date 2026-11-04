"""Canonical reference gallery scroll behavior in the CAP editor."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSplitter

from vscs.presentation.widgets.canonical_reference_gallery import (
    CanonicalReferenceGallery,
)


def test_reference_gallery_has_independent_scrolling(qtbot):
    widget = CanonicalReferenceGallery()
    qtbot.addWidget(widget)

    thumbnails = widget.gallery
    details = widget.details_scroll
    assert isinstance(details, QScrollArea)
    assert thumbnails.objectName() == "canonicalReferenceGallery"
    assert details.objectName() == "canonicalReferenceDetailsScroll"
    assert thumbnails.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert thumbnails.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert details.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert details.horizontalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert details.widgetResizable()
    assert details.widget() is not None
    assert details.widget().layout() is not None

    splitter = widget.findChild(QSplitter, "canonicalReferenceGallerySplitter")
    assert splitter is not None
    assert splitter.widget(0) is thumbnails
    assert splitter.widget(1) is details
    assert not splitter.childrenCollapsible()


def test_reference_gallery_scroll_does_not_disable_reference_actions(qtbot):
    widget = CanonicalReferenceGallery()
    qtbot.addWidget(widget)
    assert widget.primary_button.text() == "Set as Primary"
    assert widget.approve_button.text() == "Approve"
    assert not widget.approve_button.isEnabled()
    assert widget.gallery.count() == 0
