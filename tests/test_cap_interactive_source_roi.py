"""F5.4.2 C2: source-resolution ROI selection has no generation authority."""

import hashlib
from decimal import Decimal

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QRect, Qt

from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError
from vscs.application.caps.human_reviewed_mask_evidence import _pixel_edge
from vscs.presentation.dialogs.source_image_roi_dialog import (
    SourceImageRoiDialog,
    pixel_rect_to_region,
)


def _candidate(tmp_path):
    directory = tmp_path / "Canonical Assets" / "STORY-ROI" / "Images" / "Visual Candidates"
    directory.mkdir(parents=True)
    source = directory / "test.png"
    Image.new("RGB", (1392, 752), (40, 50, 60)).save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return source, digest


def test_pixel_rectangle_converts_to_normalized_source_coordinates():
    region = pixel_rect_to_region(QRect(575, 240, 84, 48), source_width=1392, source_height=752)
    assert region.x == 575 / 1392
    assert region.y == 240 / 752
    assert region.width == 84 / 1392
    assert region.height == 48 / 752


@pytest.mark.parametrize(
    "bounds",
    [
        QRect(0, 0, 1, 10),
        QRect(0, 0, 10, 1),
        QRect(-1, 0, 10, 10),
        QRect(1390, 740, 5, 20),
    ],
)
def test_invalid_source_rectangle_rejected(bounds):
    with pytest.raises(GeometryCorrectionError):
        pixel_rect_to_region(bounds, source_width=1392, source_height=752)


def test_selector_uses_true_source_pixels_and_requires_apply(qtbot, tmp_path):
    source, digest = _candidate(tmp_path)
    original = source.read_bytes()
    dialog = SourceImageRoiDialog(source_path=source, expected_source_sha256=digest)
    qtbot.addWidget(dialog)
    assert dialog.canvas.size().width() == 1392
    assert dialog.canvas.size().height() == 752
    assert not dialog.apply_button.isEnabled()
    assert dialog.selected_region is None
    qtbot.mousePress(dialog.canvas, Qt.MouseButton.LeftButton, pos=QPoint(650, 300))
    qtbot.mouseMove(dialog.canvas, QPoint(575, 240))
    qtbot.mouseRelease(dialog.canvas, Qt.MouseButton.LeftButton, pos=QPoint(575, 240))
    assert dialog.apply_button.isEnabled()
    assert dialog.canvas.selected_bounds == QRect(575, 240, 75, 60)
    assert "575,240" in dialog.readout.text()
    assert dialog.selected_region is None
    dialog.apply_button.click()
    assert dialog.selected_region is not None
    assert dialog.selected_region.x == 575 / 1392
    assert dialog.selected_region.y == 240 / 752
    assert source.read_bytes() == original
    assert list(source.parent.glob("*.png")) == [source]


def test_selector_cancel_discards_uncommitted_roi(qtbot, tmp_path):
    source, digest = _candidate(tmp_path)
    dialog = SourceImageRoiDialog(source_path=source, expected_source_sha256=digest)
    qtbot.addWidget(dialog)
    qtbot.mousePress(dialog.canvas, Qt.MouseButton.LeftButton, pos=QPoint(200, 200))
    qtbot.mouseRelease(dialog.canvas, Qt.MouseButton.LeftButton, pos=QPoint(220, 220))
    dialog.reject()
    assert dialog.selected_region is None


def test_selector_refuses_stale_source_before_display(qtbot, tmp_path):
    source, digest = _candidate(tmp_path)
    Image.new("RGB", (1392, 752), (80, 70, 60)).save(source)
    with pytest.raises(GeometryCorrectionError, match="changed"):
        SourceImageRoiDialog(source_path=source, expected_source_sha256=digest)


def test_selector_rejects_changed_source_on_apply(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    source, digest = _candidate(tmp_path)
    dialog = SourceImageRoiDialog(source_path=source, expected_source_sha256=digest)
    qtbot.addWidget(dialog)
    qtbot.mousePress(dialog.canvas, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
    qtbot.mouseRelease(dialog.canvas, Qt.MouseButton.LeftButton, pos=QPoint(60, 60))
    source.write_bytes(b"tampered after opening")
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *_args: warnings.append(True))
    dialog.apply_button.click()
    assert warnings
    assert dialog.selected_region is None


def test_normalized_drag_edges_roundtrip_to_original_integer_pixels():
    region = pixel_rect_to_region(QRect(575, 240, 84, 48), source_width=1392, source_height=752)
    assert _pixel_edge(Decimal(str(region.x)) * 1392, upper=False) == 575
    assert (
        _pixel_edge(
            (Decimal(str(region.x)) + Decimal(str(region.width))) * 1392,
            upper=True,
        )
        == 659
    )
    assert _pixel_edge(Decimal(str(region.y)) * 752, upper=False) == 240
    assert (
        _pixel_edge(
            (Decimal(str(region.y)) + Decimal(str(region.height))) * 752,
            upper=True,
        )
        == 288
    )
