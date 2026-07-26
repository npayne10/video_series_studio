"""Dialog for generating versioned canonical image candidates."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vscs.domain.caps import CanonicalAssetGenerationRequest


class CanonicalAssetGenerationDialog(QDialog):
    """Collect provider-neutral canonical image generation settings."""

    def __init__(self, default_prompt: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Canonical Images")
        self.setMinimumWidth(680)

        self.prompt = QTextEdit(default_prompt)
        self.prompt.setMinimumHeight(150)
        self.negative_prompt = QTextEdit()
        self.negative_prompt.setMaximumHeight(90)
        self.model = QLineEdit("VSCS Local Preview")
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_147_483_647)
        self.width = QSpinBox()
        self.width.setRange(256, 8192)
        self.width.setValue(1280)
        self.height = QSpinBox()
        self.height.setRange(256, 8192)
        self.height.setValue(720)
        self.variations = QSpinBox()
        self.variations.setRange(1, 12)
        self.variations.setValue(1)

        form = QFormLayout()
        form.addRow("Prompt", self.prompt)
        form.addRow("Negative prompt", self.negative_prompt)
        form.addRow("Provider/model", self.model)
        form.addRow("Seed", self.seed)
        form.addRow("Width", self.width)
        form.addRow("Height", self.height)
        form.addRow("Variations", self.variations)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def request_value(self) -> CanonicalAssetGenerationRequest:
        return CanonicalAssetGenerationRequest(
            prompt=self.prompt.toPlainText(),
            negative_prompt=self.negative_prompt.toPlainText(),
            model=self.model.text(),
            seed=self.seed.value(),
            width=self.width.value(),
            height=self.height.value(),
            variations=self.variations.value(),
        )

    def _validate(self) -> None:
        try:
            self.request_value()
        except ValueError:
            self.prompt.setFocus()
            return
        self.accept()
