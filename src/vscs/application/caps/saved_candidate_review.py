"""Reopen previously paid Candidate evaluations without re-running AI or CIEE.

Only the original immutable quality report is reconstructed, and only when its
image hash, CAP review, status and lineage still match the current snapshot.
No network, new evaluation, record mutation or correction attempt occurs.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from vscs.application.caps.visual_candidate_quality import (
    CandidateQualityError,
    CandidateQualityResult,
    CandidateQualityReviewService,
)
from vscs.application.ciee.models import (
    CanonicalImageEvaluation,
    EvaluationDecision,
    EvaluationMetric,
)
from vscs.application.siee.models import SemanticImageEvaluation


def _same_path(value: object, expected: Path) -> bool:
    return isinstance(value, str) and Path(value) == expected


def reopen_saved_candidate_review(
    quality: CandidateQualityReviewService,
    asset_id: str,
    reference_id: int,
) -> tuple[CandidateQualityResult, Path]:
    """Load most recent *current* saved semantic review, never create a new one."""
    snapshot = quality.snapshot(asset_id, reference_id)
    root = snapshot.project_root / "Canonical Assets" / asset_id / ".metadata" / "evaluation"
    if root.is_symlink() or not root.is_dir():
        raise CandidateQualityError("Saved Candidate review directory unavailable")
    pattern = f"{snapshot.image_path.stem}.*.candidate_quality.json"
    candidates = sorted(
        root.glob(pattern),
        key=lambda p: (p.stat().st_mtime_ns, p.name),
        reverse=True,
    )
    if not candidates:
        raise CandidateQualityError(
            "No saved Candidate semantic review available; a new review requires separate consent"
        )
    # Never fall back to an older report after encountering a current, stale,
    # or malformed newer record. The newest report is the only eligible result.
    path = candidates[0]
    if path.is_symlink() or path.parent != root or not path.is_file():
        raise CandidateQualityError("Saved Candidate review path is unsafe")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CandidateQualityError("Saved Candidate review cannot be read") from exc
    if not isinstance(data, dict):
        raise CandidateQualityError("Saved Candidate review is malformed")
    expected_fields = (
        ("schema_version", 1),
        ("evaluation_type", "vscs_cap_visual_candidate_quality"),
        ("governance", "advisory_only_no_approval"),
        ("asset_id", asset_id),
        ("reference_id", reference_id),
        ("reference_role", snapshot.reference_role),
        ("reference_status", snapshot.reference_status),
        ("image_sha256", snapshot.image_sha256),
        ("specification_fingerprint", snapshot.specification_fingerprint),
        ("review_fingerprint", snapshot.review_fingerprint),
        ("reviewed_fields", dict(snapshot.accepted_fields)),
        ("deferred_fields", list(snapshot.deferred_fields)),
        ("continuity", list(snapshot.continuity)),
        ("related_asset_ids", list(snapshot.dependencies)),
    )
    if any(data.get(key) != value for key, value in expected_fields):
        raise CandidateQualityError("Saved review is stale: Candidate or reviewed CAP changed")
    if data.get("image") != str(snapshot.image_path.relative_to(snapshot.project_root)):
        raise CandidateQualityError("Saved review image path does not match")
    technical = data.get("technical")
    semantic = data.get("semantic")
    if not isinstance(technical, dict) or not isinstance(semantic, dict):
        raise CandidateQualityError(
            "Saved review requires existing technical and semantic evidence"
        )
    if (
        not _same_path(technical.get("image_path"), snapshot.image_path)
        or technical.get("asset_id") != asset_id
        or technical.get("category") != snapshot.category.value
        or not _same_path(semantic.get("image_path"), snapshot.image_path)
        or semantic.get("asset_id") != asset_id
        or semantic.get("category") != snapshot.category.value
    ):
        raise CandidateQualityError("Saved report has inconsistent image or asset identity")
    try:
        metrics = technical["metrics"]
        if not isinstance(metrics, list) or not metrics:
            raise ValueError("missing technical metrics")
        reconstructed = CanonicalImageEvaluation(
            image_path=snapshot.image_path,
            asset_id=asset_id,
            category=snapshot.category,
            width=technical["width"],
            height=technical["height"],
            overall_score=technical["overall_score"],
            decision=EvaluationDecision(technical["decision"]),
            metrics=tuple(
                EvaluationMetric(
                    name=item["name"],
                    score=item["score"],
                    summary=item["summary"],
                    blocking=item["blocking"],
                )
                for item in metrics
            ),
            warnings=tuple(technical["warnings"]),
            manual_checks=tuple(technical["manual_checks"]),
            engine_version=technical.get("engine_version", "1.0"),
        )
        restored_semantic = SemanticImageEvaluation.model_validate(semantic)
        recommendations = data["recommendations"]
        if (
            type(reconstructed.width) is not int
            or type(reconstructed.height) is not int
            or reconstructed.width <= 0
            or reconstructed.height <= 0
            or type(reconstructed.overall_score) is not int
            or not 0 <= reconstructed.overall_score <= 100
            or not all(
                type(item.score) is int and 0 <= item.score <= 100 for item in reconstructed.metrics
            )
            or not isinstance(recommendations, list)
            or not all(isinstance(item, str) for item in recommendations)
        ):
            raise ValueError("invalid report evidence fields")
        result = CandidateQualityResult(
            snapshot=snapshot,
            technical=reconstructed,
            semantic=restored_semantic,
            recommendations=tuple(recommendations),
        )
        if result.decision != data.get("decision"):
            raise ValueError("saved quality decision mismatch")
        # Full round-trip equality detects missing/changed model fields rather
        # than silently repairing an incomplete saved report.
        for key in (
            "technical",
            "semantic",
            "decision",
            "recommendations",
            "correction_comparison",
            "approved_primary_reference",
        ):
            if result.as_dict()[key] != data.get(key):
                raise ValueError(f"saved report {key} differs from reconstructed evidence")
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise CandidateQualityError("Saved Candidate review evidence is invalid") from exc
    return result, path
