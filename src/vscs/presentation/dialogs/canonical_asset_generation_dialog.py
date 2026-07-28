"""Dialog for generating versioned canonical image candidates."""

from __future__ import annotations

from typing import Any

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

from vscs.application.caie import CanonicalAssetIntelligenceEngine, CanonicalPromptContext
from vscs.domain.caps import CanonicalAssetGenerationRequest


class CanonicalAssetGenerationDialog(QDialog):
    """Review CAIE-compiled prompts and collect XCIC generation settings."""

    def __init__(
        self,
        default_prompt: str = "",
        parent: QWidget | None = None,
        *,
        default_negative_prompt: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Generate Canonical Images with XCIC")
        self.setMinimumWidth(680)

        compiled_prompt, compiled_negative = self._compile_from_parent(
            parent,
            default_prompt,
            default_negative_prompt,
        )

        self.prompt = QTextEdit(compiled_prompt)
        self.prompt.setMinimumHeight(210)
        self.prompt.setToolTip(
            "CAIE compiled this prompt from the registered asset and CAP. "
            "You may refine it before rendering."
        )
        self.negative_prompt = QTextEdit(
            compiled_negative
            or (
                "fantasy, magical, stylised science fiction, excessive glow, neon technology, "
                "unnecessary holograms, floating interfaces, impossible architecture, cartoon, "
                "anime, illustration, low detail, low resolution, distorted geometry, watermark, "
                "logo, AI artifacts, identity drift, inconsistent materials, inconsistent scale"
            )
        )
        self.negative_prompt.setMaximumHeight(120)
        self.model = QLineEdit("Qwen Image 2512 via XCIC")
        self.seed = QSpinBox()
        self.seed.setRange(0, 2_147_483_647)
        self.width = QSpinBox()
        self.width.setRange(256, 8192)
        self.width.setValue(1664)
        self.height = QSpinBox()
        self.height.setRange(256, 8192)
        self.height.setValue(928)
        self.variations = QSpinBox()
        self.variations.setRange(1, 12)
        self.variations.setValue(1)

        form = QFormLayout()
        form.addRow("CAIE compiled prompt", self.prompt)
        form.addRow("CAIE negative prompt", self.negative_prompt)
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

    @staticmethod
    def _compile_from_parent(
        parent: QWidget | None,
        fallback_prompt: str,
        fallback_negative: str,
    ) -> tuple[str, str]:
        """Compile a preview from the active CAP editor when services are available."""
        try:
            editor: Any = parent
            profile = getattr(editor, "profile", None)
            reference_service = getattr(editor, "reference_service", None)
            if profile is None or reference_service is None:
                return fallback_prompt, fallback_negative
            asset = reference_service.caps.assets.get(profile.asset_id)
            package = CanonicalAssetIntelligenceEngine().compile(
                CanonicalPromptContext(
                    asset=asset,
                    profile=profile,
                    target_model="Qwen Image 2512 via XCIC",
                )
            )
            return package.positive_prompt, package.negative_prompt
        except Exception:
            # The application service still compiles CAIE again before rendering. Falling back here
            # keeps the dialog usable if it is opened without a fully initialized CAP editor.
            return fallback_prompt, fallback_negative

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
