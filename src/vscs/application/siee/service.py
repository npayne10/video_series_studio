"""Semantic image evaluation orchestration."""

from __future__ import annotations

from pathlib import Path

from vscs.application.siee.models import (
    SemanticDecision,
    SemanticImageEvaluation,
    SemanticMetric,
)
from vscs.application.siee.provider import SemanticEvaluationProvider
from vscs.domain.assets import AssetCategory


class SIEEError(RuntimeError):
    """Raised when semantic evaluation cannot be completed."""


class SemanticImageEvaluationEngine:
    VERSION = "1.0"

    def __init__(self, provider: SemanticEvaluationProvider) -> None:
        self.provider = provider

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
    ) -> SemanticImageEvaluation:
        try:
            result = self.provider.evaluate(
                image_path,
                asset_id=asset_id,
                asset_name=asset_name,
                category=category,
                canonical_description=canonical_description,
                visual_identity=visual_identity,
                production_notes=production_notes,
                generation_prompt=generation_prompt,
                primary_reference_path=primary_reference_path,
            )
        except Exception as exc:
            raise SIEEError(str(exc)) from exc

        metrics: tuple[SemanticMetric, ...] = (
            result.prompt_adherence,
            result.category_validity,
            result.visible_text,
            result.canon_consistency,
            result.engineering_plausibility,
            result.cinematic_quality,
        )
        overall = round(sum(metric.score for metric in metrics) / len(metrics))
        blocking = any(metric.blocking for metric in metrics)
        if blocking or overall < 55:
            decision = SemanticDecision.REGENERATE
        elif overall < 80:
            decision = SemanticDecision.REVIEW
        else:
            decision = SemanticDecision.PASS

        return SemanticImageEvaluation(
            image_path=image_path,
            asset_id=asset_id,
            category=category,
            provider=self.provider.provider_name,
            model=self.provider.model_name,
            overall_score=overall,
            decision=decision,
            metrics=metrics,
            detected_features=result.detected_features,
            violations=result.violations,
            recommendations=result.recommendations,
            summary=result.summary,
            primary_reference_path=primary_reference_path,
            engine_version=self.VERSION,
        )
