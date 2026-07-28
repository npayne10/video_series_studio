from __future__ import annotations

import json
from pathlib import Path

from vscs.application.pre import CanonRisk, ProductionDecision, ProductionReadinessEngine


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_pre_combines_ciee_and_siee(tmp_path: Path) -> None:
    technical = _write(
        tmp_path / "image.ciee.json",
        {"overall_score": 90, "metrics": [], "warnings": []},
    )
    semantic = _write(
        tmp_path / "image.siee.json",
        {
            "overall_score": 86,
            "metrics": [
                {"name": "Canon consistency", "score": 88, "summary": "Good", "blocking": False}
            ],
            "violations": [],
            "recommendations": [],
        },
    )

    report = ProductionReadinessEngine().evaluate(
        image_path=tmp_path / "image.png",
        asset_id="CAP-SHP-001",
        reference_id=7,
        technical_report_path=technical,
        semantic_report_path=semantic,
    )

    assert report.overall_score == 88
    assert report.decision is ProductionDecision.PASS
    assert report.canon_risk is CanonRisk.LOW


def test_pre_regenerates_on_blocking_failure(tmp_path: Path) -> None:
    technical = _write(
        tmp_path / "image.ciee.json",
        {
            "overall_score": 95,
            "metrics": [
                {"name": "Exposure", "score": 10, "summary": "Almost black", "blocking": True}
            ],
            "warnings": ["Almost black"],
        },
    )
    semantic = _write(
        tmp_path / "image.siee.json",
        {
            "overall_score": 90,
            "metrics": [
                {"name": "Canon consistency", "score": 90, "summary": "Good", "blocking": False}
            ],
            "violations": [],
            "recommendations": [],
        },
    )

    report = ProductionReadinessEngine().evaluate(
        image_path=tmp_path / "image.png",
        asset_id="CAP-SHP-001",
        reference_id=8,
        technical_report_path=technical,
        semantic_report_path=semantic,
    )

    assert report.decision is ProductionDecision.REGENERATE
    assert report.blocking_reasons
