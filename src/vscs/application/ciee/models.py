"""Stable contracts for the Canonical Image Evaluation Engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from vscs.domain.assets import AssetCategory


class EvaluationDecision(StrEnum):
    """Production recommendation produced by CIEE."""

    PASS = "pass"
    REVIEW = "review"
    REGENERATE = "regenerate"


@dataclass(frozen=True, slots=True)
class EvaluationMetric:
    """One scored quality dimension."""

    name: str
    score: int
    summary: str
    blocking: bool = False


@dataclass(frozen=True, slots=True)
class CanonicalImageEvaluation:
    """Complete CIEE report for one canonical image."""

    image_path: Path
    asset_id: str
    category: AssetCategory
    width: int
    height: int
    overall_score: int
    decision: EvaluationDecision
    metrics: tuple[EvaluationMetric, ...]
    warnings: tuple[str, ...]
    manual_checks: tuple[str, ...]
    engine_version: str = "1.0"

    def as_dict(self) -> dict[str, object]:
        return {
            "engine": "Canonical Image Evaluation Engine",
            "engine_version": self.engine_version,
            "image_path": str(self.image_path),
            "asset_id": self.asset_id,
            "category": self.category.value,
            "width": self.width,
            "height": self.height,
            "overall_score": self.overall_score,
            "decision": self.decision.value,
            "metrics": [
                {
                    "name": metric.name,
                    "score": metric.score,
                    "summary": metric.summary,
                    "blocking": metric.blocking,
                }
                for metric in self.metrics
            ],
            "warnings": list(self.warnings),
            "manual_checks": list(self.manual_checks),
        }
