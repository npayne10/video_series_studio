"""Provider contract for semantic image evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from vscs.application.siee.models import SemanticModelResult
from vscs.domain.assets import AssetCategory


class SemanticEvaluationProvider(Protocol):
    provider_name: str
    model_name: str

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
    ) -> SemanticModelResult: ...
