"""Tests for Semantic Image Evaluation Engine v1.0."""

from pathlib import Path

from vscs.application.siee import (
    SemanticDecision,
    SemanticImageEvaluationEngine,
    SemanticMetric,
    SemanticModelResult,
)
from vscs.domain.assets import AssetCategory


class StubProvider:
    provider_name = "Stub Vision"
    model_name = "stub-vision-1"

    def __init__(self, result: SemanticModelResult) -> None:
        self.result = result

    def evaluate(self, image_path: Path, **_: object) -> SemanticModelResult:
        return self.result


def _metric(name: str, score: int, *, blocking: bool = False) -> SemanticMetric:
    return SemanticMetric(name=name, score=score, summary=f"{name} summary", blocking=blocking)


def _result(score: int = 90, *, blocking: bool = False) -> SemanticModelResult:
    return SemanticModelResult(
        prompt_adherence=_metric("Prompt adherence", score, blocking=blocking),
        category_validity=_metric("Category validity", score),
        visible_text=_metric("Visible text", score),
        canon_consistency=_metric("Canon consistency", score),
        engineering_plausibility=_metric("Engineering plausibility", score),
        cinematic_quality=_metric("Cinematic quality", score),
        detected_features=("orbital spacecraft",),
        violations=(),
        recommendations=("Approve after human review",),
        summary="Candidate follows the requested canonical design.",
    )


def test_siee_passes_high_scoring_candidate() -> None:
    report = SemanticImageEvaluationEngine(StubProvider(_result())).evaluate(
        Path("candidate.png"),
        asset_id="CAP-SHP-004",
        asset_name="Guild Tug Ship",
        category=AssetCategory.SHIP,
        canonical_description="Orbital tug spacecraft.",
        visual_identity="Industrial Guild design.",
        production_notes="No maritime styling.",
        generation_prompt="Orbital spacecraft in vacuum.",
    )

    assert report.decision is SemanticDecision.PASS
    assert report.overall_score == 90
    assert report.provider == "Stub Vision"


def test_siee_blocking_failure_requires_regeneration() -> None:
    report = SemanticImageEvaluationEngine(StubProvider(_result(92, blocking=True))).evaluate(
        Path("candidate.png"),
        asset_id="CAP-SHP-004",
        asset_name="Guild Tug Ship",
        category=AssetCategory.SHIP,
        canonical_description="Orbital tug spacecraft.",
        visual_identity="Industrial Guild design.",
        production_notes="No maritime styling.",
        generation_prompt="Orbital spacecraft in vacuum.",
    )

    assert report.decision is SemanticDecision.REGENERATE
