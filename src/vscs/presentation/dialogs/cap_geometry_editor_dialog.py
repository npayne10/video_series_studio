"""Structured operator editor for non-authoritative, millimetre CAP geometry."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.application.caps.geometry_contract import CAPGeometry, SpatialAnchor


class CAPGeometryEditorDialog(QDialog):
    """Edit typed bounds and anchors without persisting or approving a CAP."""

    def __init__(self, geometry: CAPGeometry | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Draft CAP Geometry — Structured Editor (mm)")
        self.resize(580, 500)
        self.frame = QLineEdit(geometry.frame_id if geometry else "")
        self.frame.setPlaceholderText("Shared coordinate frame ID")
        self.origin: dict[str, QDoubleSpinBox] = {}
        self.dimensions: dict[str, QDoubleSpinBox] = {}
        form = QFormLayout()
        form.addRow("Coordinate frame", self.frame)
        for axis in ("x", "y", "z"):
            origin = QDoubleSpinBox()
            origin.setRange(-1_000_000_000, 1_000_000_000)
            origin.setDecimals(2)
            origin.setSuffix(" mm")
            origin.setValue(getattr(geometry.origin_mm, axis) if geometry else 0)
            self.origin[axis] = origin
            form.addRow(f"Origin {axis.upper()}", origin)
        for axis in ("x", "y", "z"):
            dimension = QDoubleSpinBox()
            dimension.setRange(0.01, 1_000_000_000)
            dimension.setDecimals(2)
            dimension.setSuffix(" mm")
            dimension.setValue(getattr(geometry.size_mm, axis) if geometry else 1000)
            self.dimensions[axis] = dimension
            form.addRow(f"Size {axis.upper()}", dimension)
        self.anchors = QTextEdit()
        self.anchors.setPlaceholderText("One anchor per line: name|x|y|z (millimetres)")
        self.anchors.setPlainText(
            "\n".join(
                f"{anchor.name}|{anchor.position_mm.x:g}|{anchor.position_mm.y:g}|"
                f"{anchor.position_mm.z:g}"
                for anchor in geometry.anchors
            )
            if geometry else ""
        )
        form.addRow("Named anchors", self.anchors)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self._apply)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)
        self.result_geometry: CAPGeometry | None = None

    def _apply(self) -> None:
        try:
            anchors: list[SpatialAnchor] = []
            for line in self.anchors.toPlainText().splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split("|")]
                if len(parts) != 4:
                    raise ValueError("Anchor lines require name|x|y|z")
                anchors.append(
                    SpatialAnchor.model_validate(
                        {
                            "name": parts[0],
                            "position_mm": dict(
                                zip(
                                    ("x", "y", "z"),
                                    (float(value) for value in parts[1:]),
                                    strict=True,
                                )
                            ),
                        }
                    )
                )
            data = {
                "frame_id": self.frame.text().strip(),
                "origin_mm": {axis: widget.value() for axis, widget in self.origin.items()},
                "size_mm": {axis: widget.value() for axis, widget in self.dimensions.items()},
                "anchors": [anchor.model_dump(mode="json") for anchor in anchors],
            }
            self.result_geometry = CAPGeometry.model_validate(data)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Draft Geometry", str(exc))
            return
        self.accept()
