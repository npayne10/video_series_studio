"""Tests for the Canonical Image Evaluation Engine."""

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from vscs.application.ciee import CanonicalImageEvaluationEngine, EvaluationDecision
from vscs.domain.assets import AssetCategory


def _save_gradient(path: Path, width: int = 1280, height: int = 720) -> None:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    for y in range(height):
        for x in range(width):
            value = int(255 * x / max(1, width - 1))
            image.setPixelColor(x, y, QColor(value, value, value))
    assert image.save(str(path))


def test_ciee_evaluates_valid_image_and_returns_manual_ship_checks(tmp_path: Path) -> None:
    path = tmp_path / "ship.png"
    _save_gradient(path)

    report = CanonicalImageEvaluationEngine().evaluate(
        path,
        asset_id="CAP-SHP-004",
        category=AssetCategory.SHIP,
    )

    assert report.width == 1280
    assert report.height == 720
    assert report.overall_score >= 55
    assert report.decision in {
        EvaluationDecision.PASS,
        EvaluationDecision.REVIEW,
    }
    assert any("maritime vessel" in check for check in report.manual_checks)
    assert report.as_dict()["engine_version"] == "1.0"


def test_ciee_marks_nearly_black_image_for_regeneration(tmp_path: Path) -> None:
    path = tmp_path / "black.png"
    image = QImage(1024, 1024, QImage.Format.Format_RGB32)
    image.fill(QColor(0, 0, 0))
    assert image.save(str(path))

    report = CanonicalImageEvaluationEngine().evaluate(
        path,
        asset_id="CAP-SHP-004",
        category=AssetCategory.SHIP,
    )

    assert report.decision is EvaluationDecision.REGENERATE
    assert any(metric.blocking for metric in report.metrics)
