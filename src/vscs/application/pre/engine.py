"""Combined Production Readiness Evaluation engine."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vscs.application.pre.models import (
    CanonRisk,
    ProductionDecision,
    ProductionReadinessReport,
    ReadinessState,
)


class PREError(RuntimeError):
    """Raised when production readiness cannot be calculated."""


class ProductionReadinessEngine:
    """Combine persisted CIEE and SIEE reports into one production decision."""

    VERSION = "1.0"

    def evaluate(
        self,
        *,
        image_path: Path,
        asset_id: str,
        reference_id: int,
        technical_report_path: Path,
        semantic_report_path: Path,
        locked: bool = False,
    ) -> ProductionReadinessReport:
        technical = self._load(technical_report_path, "CIEE")
        semantic = self._load(semantic_report_path, "SIEE")

        technical_score = self._score(technical, "overall_score", "CIEE")
        semantic_score = self._score(semantic, "overall_score", "SIEE")
        canon_score = self._canon_score(semantic)
        blocking = self._blocking_reasons(technical, semantic)

        # Canon is represented separately but is also part of semantic judgement.
        overall = round(technical_score * 0.30 + semantic_score * 0.50 + canon_score * 0.20)
        risk = self._canon_risk(canon_score, semantic)

        if blocking or risk is CanonRisk.CRITICAL or overall < 55:
            decision = ProductionDecision.REGENERATE
        elif overall < 80 or risk in {CanonRisk.HIGH, CanonRisk.MEDIUM}:
            decision = ProductionDecision.REVIEW
        else:
            decision = ProductionDecision.PASS

        if locked:
            state = ReadinessState.CANON_LOCKED
        elif decision is ProductionDecision.PASS:
            state = ReadinessState.PRODUCTION_READY
        elif decision is ProductionDecision.REVIEW:
            state = ReadinessState.CANDIDATE
        else:
            state = ReadinessState.DEVELOPMENT

        recommendations = self._recommendations(technical, semantic, risk, blocking)
        return ProductionReadinessReport(
            image_path=image_path,
            asset_id=asset_id,
            reference_id=reference_id,
            technical_score=technical_score,
            semantic_score=semantic_score,
            canon_score=canon_score,
            overall_score=overall,
            decision=decision,
            canon_risk=risk,
            readiness_state=state,
            blocking_reasons=blocking,
            recommendations=recommendations,
            technical_report_path=technical_report_path,
            semantic_report_path=semantic_report_path,
            engine_version=self.VERSION,
        )

    @staticmethod
    def _load(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise PREError(f"{label} report not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PREError(f"Unable to read {label} report {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise PREError(f"{label} report must contain a JSON object: {path}")
        return payload

    @staticmethod
    def _score(payload: dict[str, Any], field: str, label: str) -> int:
        value = payload.get(field)
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise PREError(f"{label} report has an invalid {field}: {value!r}")
        return value

    @staticmethod
    def _canon_score(semantic: dict[str, Any]) -> int:
        metrics = semantic.get("metrics", [])
        if isinstance(metrics, list):
            for metric in metrics:
                if isinstance(metric, dict) and str(metric.get("name", "")).casefold() == "canon consistency":
                    score = metric.get("score")
                    if isinstance(score, int) and 0 <= score <= 100:
                        return score
        return int(semantic.get("overall_score", 0))

    @staticmethod
    def _blocking_reasons(technical: dict[str, Any], semantic: dict[str, Any]) -> tuple[str, ...]:
        reasons: list[str] = []
        for label, payload in (("Technical", technical), ("Semantic", semantic)):
            metrics = payload.get("metrics", [])
            if not isinstance(metrics, list):
                continue
            for metric in metrics:
                if isinstance(metric, dict) and metric.get("blocking") is True:
                    reasons.append(f"{label}: {metric.get('name', 'blocking failure')} — {metric.get('summary', '')}".strip())
        return tuple(reasons)

    @staticmethod
    def _canon_risk(canon_score: int, semantic: dict[str, Any]) -> CanonRisk:
        violations = semantic.get("violations", [])
        count = len(violations) if isinstance(violations, list) else 0
        if canon_score < 45 or count >= 4:
            return CanonRisk.CRITICAL
        if canon_score < 65 or count >= 2:
            return CanonRisk.HIGH
        if canon_score < 82 or count == 1:
            return CanonRisk.MEDIUM
        return CanonRisk.LOW

    @staticmethod
    def _recommendations(
        technical: dict[str, Any],
        semantic: dict[str, Any],
        risk: CanonRisk,
        blocking: tuple[str, ...],
    ) -> tuple[str, ...]:
        values: list[str] = []
        raw = semantic.get("recommendations", [])
        if isinstance(raw, list):
            values.extend(str(value).strip() for value in raw if str(value).strip())
        warnings = technical.get("warnings", [])
        if isinstance(warnings, list):
            values.extend(f"Resolve technical issue: {value}" for value in warnings if str(value).strip())
        if risk in {CanonRisk.HIGH, CanonRisk.CRITICAL}:
            values.append("Do not approve as a canon-locked Primary until canon violations are resolved.")
        if blocking:
            values.append("Regenerate after resolving every blocking evaluation failure.")
        return tuple(dict.fromkeys(values))
