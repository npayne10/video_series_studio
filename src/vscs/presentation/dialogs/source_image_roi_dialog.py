"""Human-drawn, source-hash-bound ROI selection for Stage B / Stage C2.

Pixel-space selection is always at 100% source resolution. The dialog does
not create images, masks, saved review records, API calls or attempt authority.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import override

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError
from vscs.application.caps.spatial_visual_evidence import NormalizedRegion


def pixel_rect_to_region(rect: QRect, *, source_width: int, source_height: int) -> NormalizedRegion:
    """Convert a half-open pixel rectangle into a normalized source-image ROI."""
    if (
        type(source_width) is not int
        or type(source_height) is not int
        or source_width <= 0
        or source_height <= 0
        or rect.width() < 2
        or rect.height() < 2
        or rect.x() < 0
        or rect.y() < 0
        or rect.x() + rect.width() > source_width
        or rect.y() + rect.height() > source_height
    ):
        raise GeometryCorrectionError("ROI requires a nonempty rectangle inside the source")
    return NormalizedRegion(
        x=rect.x() / source_width,
        y=rect.y() / source_height,
        width=rect.width() / source_width,
        height=rect.height() / source_height,
    )


class SourceImageRoiCanvas(QWidget):
    """Actual-size image canvas. Drag selects half-open source pixel boundaries."""

    selection_changed = Signal()

    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image = pixmap
        self._anchor: QPoint | None = None
        self._drag_end: QPoint | None = None
        self.selected_bounds: QRect | None = None
        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setObjectName("stageC2RoiSourceCanvas")

    def _point(self, event: QMouseEvent) -> QPoint:
        p = event.position().toPoint()
        return QPoint(
            max(0, min(self._image.width(), p.x())),
            max(0, min(self._image.height(), p.y())),
        )

    def _rect(self, a: QPoint, b: QPoint) -> QRect:
        return QRect(
            min(a.x(), b.x()),
            min(a.y(), b.y()),
            abs(a.x() - b.x()),
            abs(a.y() - b.y()),
        )

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._anchor = self._point(event)
            self._drag_end = self._anchor
            self.selected_bounds = None
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._anchor is not None:
            self._drag_end = self._point(event)
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._anchor is not None:
            self._drag_end = self._point(event)
            candidate = self._rect(self._anchor, self._drag_end)
            self.selected_bounds = (
                candidate if candidate.width() >= 2 and candidate.height() >= 2 else None
            )
            self._anchor = None
            self._drag_end = None
            self.update()
            self.selection_changed.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            painter.drawPixmap(0, 0, self._image)
            shown = self.selected_bounds
            if self._anchor is not None and self._drag_end is not None:
                shown = self._rect(self._anchor, self._drag_end)
            if shown is not None and not shown.isEmpty():
                painter.fillRect(shown, QColor(255, 50, 50, 75))
                painter.setPen(QPen(QColor(255, 30, 30), 2))
                painter.drawRect(shown.adjusted(0, 0, -1, -1))
        finally:
            painter.end()


class SourceImageRoiDialog(QDialog):
    """Selection is an uncommitted proposal until the operator clicks Apply."""

    def __init__(
        self,
        *,
        source_path: Path,
        expected_source_sha256: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("stageC2InteractiveRoiDialog")
        self.setWindowTitle("F5.4.2 — Select Source Image ROI (No Generation)")
        self.resize(1050, 800)
        self.selected_region: NormalizedRegion | None = None
        self.selected_pixel_bounds: QRect | None = None

        try:
            raw = source_path.read_bytes()
        except OSError as exc:
            raise GeometryCorrectionError("Cannot open source Candidate image") from exc
        if hashlib.sha256(raw).hexdigest() != expected_source_sha256:
            raise GeometryCorrectionError("Source Candidate changed; ROI selection blocked")
        pixmap = QPixmap()
        if not pixmap.loadFromData(raw, b"PNG") or pixmap.isNull():
            raise GeometryCorrectionError("Candidate PNG could not be decoded")
        if not 0 < pixmap.width() * pixmap.height() <= 40_000_000:
            raise GeometryCorrectionError("Source image dimensions exceed safe limit")

        self._source_path = source_path
        self._source_hash = expected_source_sha256
        self.canvas = SourceImageRoiCanvas(pixmap, self)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Source: {pixmap.width()} x {pixmap.height()} px — 100% resolution. "
                "Scroll to the target and drag a tight rectangle around the editable area."
            )
        )
        area = QScrollArea(self)
        area.setWidgetResizable(False)
        area.setWidget(self.canvas)
        area.setObjectName("stageC2RoiSourceScroll")
        layout.addWidget(area, 1)
        self.readout = QLabel("No selection. Drag on the original-resolution image.", self)
        self.readout.setObjectName("stageC2RoiSelectionReadout")
        layout.addWidget(self.readout)
        layout.addWidget(
            QLabel(
                "This proposes an ROI only. It does not approve a mask, "
                "call AI, register a Candidate or consume an attempt."
            )
        )
        controls = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.apply_button = controls.button(QDialogButtonBox.StandardButton.Ok)
        self.apply_button.setText("Apply Selected ROI (No Generation)")
        self.apply_button.setObjectName("stageC2ApplySelectedROI")
        self.apply_button.setEnabled(False)
        controls.accepted.connect(self._apply)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

        # Readout is updated on mouse release, never on tentative drag.
        def update_selection() -> None:
            bounds = self.canvas.selected_bounds
            self.apply_button.setEnabled(bounds is not None)
            if bounds is not None:
                region = pixel_rect_to_region(
                    bounds,
                    source_width=pixmap.width(),
                    source_height=pixmap.height(),
                )
                self.readout.setText(
                    f"Pixel bounds: ({bounds.x()},{bounds.y()}) to "
                    f"({bounds.x() + bounds.width()},{bounds.y() + bounds.height()}) "
                    f"— ROI: {region.x:.8f},{region.y:.8f},"
                    f"{region.width:.8f},{region.height:.8f}"
                )
            else:
                self.readout.setText("Selection too small. Drag a rectangle (at least 2x2 pixels).")

        self.canvas.selection_changed.connect(update_selection)

    def _apply(self) -> None:
        bounds = self.canvas.selected_bounds
        if bounds is None:
            return
        try:
            if hashlib.sha256(self._source_path.read_bytes()).hexdigest() != self._source_hash:
                raise GeometryCorrectionError("Source Candidate changed during ROI selection")
            region = pixel_rect_to_region(
                bounds,
                source_width=self.canvas.width(),
                source_height=self.canvas.height(),
            )
        except (OSError, GeometryCorrectionError) as exc:
            QMessageBox.warning(self, "ROI Selection Blocked", str(exc))
            return
        self.selected_region = region
        self.selected_pixel_bounds = bounds
        self.accept()
