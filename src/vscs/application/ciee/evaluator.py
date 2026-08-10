"""Canonical Image Evaluation Engine v1.0."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage

from vscs.application.ciee.models import (
    CanonicalImageEvaluation,
    EvaluationDecision,
    EvaluationMetric,
)
from vscs.domain.assets import AssetCategory


class CIEEError(RuntimeError):
    """Raised when an image cannot be evaluated."""


class CanonicalImageEvaluationEngine:
    """Evaluate image integrity and technical production readiness.

    Version 1.0 deliberately performs deterministic local checks. Semantic prompt
    adherence and canon consistency remain explicit manual review items until a
    vision-capable evaluator is configured in a later phase.
    """

    VERSION = "1.0"

    def evaluate(
        self,
        image_path: Path,
        *,
        asset_id: str,
        category: AssetCategory,
    ) -> CanonicalImageEvaluation:
        path = image_path.expanduser().resolve(strict=False)
        if not path.is_file():
            raise CIEEError(f"Canonical image does not exist: {path}")

        image = QImage(str(path))
        if image.isNull():
            raise CIEEError(f"Unable to decode canonical image: {path}")
        image = image.convertToFormat(QImage.Format.Format_RGB32)
        width, height = image.width(), image.height()

        sample = self._sample_luminance(image)
        if not sample:
            raise CIEEError(f"Unable to sample canonical image: {path}")

        metrics = (
            self._resolution_metric(width, height),
            self._exposure_metric(sample),
            self._contrast_metric(sample),
            self._clipping_metric(sample),
            self._detail_metric(image),
            self._aspect_metric(width, height),
        )
        blocking = any(metric.blocking for metric in metrics)
        overall = round(sum(metric.score for metric in metrics) / len(metrics))
        if blocking or overall < 55:
            decision = EvaluationDecision.REGENERATE
        elif overall < 80:
            decision = EvaluationDecision.REVIEW
        else:
            decision = EvaluationDecision.PASS

        warnings = tuple(metric.summary for metric in metrics if metric.score < 70)
        manual_checks = self._manual_checks(category)
        return CanonicalImageEvaluation(
            image_path=path,
            asset_id=asset_id,
            category=category,
            width=width,
            height=height,
            overall_score=overall,
            decision=decision,
            metrics=metrics,
            warnings=warnings,
            manual_checks=manual_checks,
            engine_version=self.VERSION,
        )

    @staticmethod
    def _sample_luminance(image: QImage) -> list[int]:
        step_x = max(1, image.width() // 160)
        step_y = max(1, image.height() // 100)
        values: list[int] = []
        for y in range(0, image.height(), step_y):
            for x in range(0, image.width(), step_x):
                colour = image.pixelColor(x, y)
                values.append(
                    round(0.2126 * colour.red() + 0.7152 * colour.green() + 0.0722 * colour.blue())
                )
        return values

    @staticmethod
    def _resolution_metric(width: int, height: int) -> EvaluationMetric:
        pixels = width * height
        if width < 512 or height < 512:
            return EvaluationMetric(
                "Resolution",
                25,
                f"Image is only {width}x{height}; minimum production review size is 512 pixels per side.",
                True,
            )
        if pixels >= 3_000_000:
            score = 100
        elif pixels >= 1_500_000:
            score = 90
        elif pixels >= 900_000:
            score = 78
        else:
            score = 65
        return EvaluationMetric("Resolution", score, f"Decoded successfully at {width}x{height}.")

    @staticmethod
    def _exposure_metric(values: list[int]) -> EvaluationMetric:
        mean = sum(values) / len(values)
        distance = abs(mean - 128)
        score = max(0, round(100 - distance * 1.15))
        blocking = mean < 10 or mean > 245
        return EvaluationMetric("Exposure", score, f"Mean luminance is {mean:.1f}/255.", blocking)

    @staticmethod
    def _contrast_metric(values: list[int]) -> EvaluationMetric:
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        deviation = variance**0.5
        score = max(0, min(100, round(deviation * 2.2)))
        return EvaluationMetric(
            "Contrast", score, f"Luminance standard deviation is {deviation:.1f}."
        )

    @staticmethod
    def _clipping_metric(values: list[int]) -> EvaluationMetric:
        clipped = sum(1 for value in values if value <= 3 or value >= 252) / len(values)
        score = max(0, round(100 - clipped * 250))
        blocking = clipped > 0.75
        return EvaluationMetric(
            "Highlight/shadow clipping",
            score,
            f"{clipped * 100:.1f}% of sampled pixels are near pure black or white.",
            blocking,
        )

    @staticmethod
    def _detail_metric(image: QImage) -> EvaluationMetric:
        step_x = max(2, image.width() // 120)
        step_y = max(2, image.height() // 80)
        differences: list[int] = []
        for y in range(0, image.height() - step_y, step_y):
            for x in range(0, image.width() - step_x, step_x):
                a = image.pixelColor(x, y)
                b = image.pixelColor(x + step_x, y)
                c = image.pixelColor(x, y + step_y)
                differences.append(abs(a.value() - b.value()) + abs(a.value() - c.value()))
        average = sum(differences) / len(differences) if differences else 0.0
        score = max(0, min(100, round(average * 2.8)))
        return EvaluationMetric(
            "Local detail", score, f"Average sampled edge variation is {average:.1f}."
        )

    @staticmethod
    def _aspect_metric(width: int, height: int) -> EvaluationMetric:
        ratio = width / height
        if 1.65 <= ratio <= 1.85:
            score = 100
            summary = f"Aspect ratio {ratio:.3f}:1 is suitable for a 16:9 production reference."
        elif 2.25 <= ratio <= 2.45:
            score = 100
            summary = f"Aspect ratio {ratio:.3f}:1 is suitable for cinematic 2.39:1 production."
        elif 0.8 <= ratio <= 1.25:
            score = 88
            summary = f"Aspect ratio {ratio:.3f}:1 is suitable for square or portrait canonical reference use."
        else:
            score = 70
            summary = f"Aspect ratio {ratio:.3f}:1 is usable but does not match common VSCS production formats."
        return EvaluationMetric("Aspect ratio", score, summary)

    @staticmethod
    def _manual_checks(category: AssetCategory) -> tuple[str, ...]:
        common = (
            "Confirm the image follows the CAIE prompt and approved CAP facts.",
            "Check for visible text, logos, watermarks, malformed lettering or UI overlays.",
            "Confirm composition, materials, scale and lighting are suitable for production continuity.",
        )
        category_checks: dict[AssetCategory, tuple[str, ...]] = {
            AssetCategory.SHIP: (
                "Confirm the subject reads as a spacecraft rather than a maritime vessel.",
                "Check propulsion, docking equipment and hull engineering for plausible spatial relationships.",
            ),
            AssetCategory.CHARACTER: (
                "Check face, hands, anatomy, age, wardrobe and identity consistency.",
            ),
            AssetCategory.LOCATION: (
                "Check architecture, access routes, scale and spatial continuity.",
            ),
            AssetCategory.PLANET: (
                "Check planetary scale, atmosphere, geology and orbital plausibility.",
            ),
        }
        return (*common, *category_checks.get(category, ()))
