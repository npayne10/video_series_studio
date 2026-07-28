"""OpenAI vision-backed provider for SIEE."""

from __future__ import annotations

import base64
import mimetypes
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from vscs.application.siee.models import SemanticModelResult
from vscs.domain.assets import AssetCategory
from vscs.infrastructure.ai.provider import AIProviderError


class OpenAISemanticImageEvaluator:
    provider_name = "OpenAI Vision"

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key.strip():
            raise ValueError("An OpenAI API key is required for semantic evaluation")
        if not model.strip():
            raise ValueError("An OpenAI vision-capable model is required")
        try:
            openai_module = import_module("openai")
            client_type = openai_module.OpenAI
        except (ImportError, AttributeError) as exc:
            raise AIProviderError(
                'Install the VSCS AI dependency with: python -m pip install "openai>=1.68"'
            ) from exc
        self._client: Any = client_type(api_key=api_key)
        self.model_name = model

    def evaluate(
        self,
        image_path: Path,
        *,
        asset_id: str,
        asset_name: str,
        category: AssetCategory,
        canonical_description: str,
        visual_identity: str,
        production_notes: str,
        generation_prompt: str,
        primary_reference_path: Path | None = None,
    ) -> SemanticModelResult:
        candidate = image_path.expanduser().resolve(strict=True)
        content: list[dict[str, object]] = [
            {
                "type": "input_text",
                "text": self._evaluation_text(
                    asset_id=asset_id,
                    asset_name=asset_name,
                    category=category,
                    canonical_description=canonical_description,
                    visual_identity=visual_identity,
                    production_notes=production_notes,
                    generation_prompt=generation_prompt,
                    has_primary=primary_reference_path is not None,
                ),
            },
            {"type": "input_image", "image_url": self._data_url(candidate), "detail": "high"},
        ]
        if primary_reference_path is not None:
            primary = primary_reference_path.expanduser().resolve(strict=True)
            content.extend(
                (
                    {
                        "type": "input_text",
                        "text": "The next image is the approved primary canonical reference. Compare identity, silhouette, proportions, materials, colours and design language against it.",
                    },
                    {"type": "input_image", "image_url": self._data_url(primary), "detail": "high"},
                )
            )
        instructions = (
            "You are the VSCS Semantic Image Evaluation Engine. Evaluate conservatively and only from visible evidence. "
            "Score each supplied dimension from 0 to 100. Mark blocking=true for decisive failures such as the wrong asset category, strong contradiction of approved canon, prominent unwanted text, severe anatomy failure, or identity mismatch. "
            "For visible_text, a score of 100 means no unwanted text is visible; lower scores mean increasingly serious unwanted lettering, captions, logos, watermarks or UI overlays. "
            "Do not invent details that cannot be seen. Keep evidence and recommendations concise and production-oriented."
        )
        try:
            response = self._client.responses.parse(
                model=self.model_name,
                instructions=instructions,
                input=[{"role": "user", "content": content}],
                text_format=SemanticModelResult,
            )
            parsed = response.output_parsed
        except Exception as exc:
            raise AIProviderError(f"OpenAI semantic image evaluation failed: {exc}") from exc
        if parsed is None:
            raise AIProviderError("OpenAI returned no structured semantic evaluation")
        return cast(SemanticModelResult, parsed)

    @staticmethod
    def _data_url(path: Path) -> str:
        media_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{encoded}"

    @staticmethod
    def _evaluation_text(
        *,
        asset_id: str,
        asset_name: str,
        category: AssetCategory,
        canonical_description: str,
        visual_identity: str,
        production_notes: str,
        generation_prompt: str,
        has_primary: bool,
    ) -> str:
        return (
            f"Candidate image to evaluate.\nAsset ID: {asset_id}\nAsset name: {asset_name}\n"
            f"Category: {category.value}\n\nCanonical description:\n{canonical_description or '(none)'}\n\n"
            f"Visual identity:\n{visual_identity or '(none)'}\n\nProduction notes:\n{production_notes or '(none)'}\n\n"
            f"Final generation prompt:\n{generation_prompt or '(unavailable)'}\n\n"
            f"Approved primary reference supplied: {'yes' if has_primary else 'no'}\n\n"
            "Evaluate prompt adherence, category validity, unwanted visible text, canon consistency, engineering plausibility, and cinematic production quality. "
            "For ships, explicitly distinguish spacecraft from terrestrial maritime vessels. For characters, inspect face, hands, anatomy, wardrobe and identity."
        )
