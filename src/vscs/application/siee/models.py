"""Stable contracts for the Semantic Image Evaluation Engine."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from vscs.domain.assets import AssetCategory


class SemanticDecision(StrEnum):
    PASS = "pass"
    REVIEW = "review"
    REGENERATE = "regenerate"


class SemanticMetric(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1)
    blocking: bool = False
    evidence: tuple[str, ...] = ()


class SemanticModelResult(BaseModel):
    """Structured result returned by a vision-capable semantic provider."""

    prompt_adherence: SemanticMetric
    category_validity: SemanticMetric
    visible_text: SemanticMetric
    canon_consistency: SemanticMetric
    engineering_plausibility: SemanticMetric
    cinematic_quality: SemanticMetric
    detected_features: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    summary: str = Field(min_length=1)


class SemanticImageEvaluation(BaseModel):
    """Persistable SIEE report for one canonical candidate."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    image_path: Path
    asset_id: str
    category: AssetCategory
    provider: str
    model: str
    overall_score: int = Field(ge=0, le=100)
    decision: SemanticDecision
    metrics: tuple[SemanticMetric, ...]
    detected_features: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()
    summary: str
    primary_reference_path: Path | None = None
    engine_version: str = "1.0"

    def as_dict(self) -> dict[str, object]:
        return {
            "engine": "Semantic Image Evaluation Engine",
            "engine_version": self.engine_version,
            "image_path": str(self.image_path),
            "asset_id": self.asset_id,
            "category": self.category.value,
            "provider": self.provider,
            "model": self.model,
            "overall_score": self.overall_score,
            "decision": self.decision.value,
            "primary_reference_path": (
                str(self.primary_reference_path) if self.primary_reference_path else None
            ),
            "metrics": [metric.model_dump(mode="json") for metric in self.metrics],
            "detected_features": list(self.detected_features),
            "violations": list(self.violations),
            "recommendations": list(self.recommendations),
            "summary": self.summary,
        }
