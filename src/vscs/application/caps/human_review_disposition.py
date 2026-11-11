"""F5.4: separately governed operator correction disposition of an advisory review.

A human disposition NEVER edits the semantic report, approves a reference or
authorizes a provider call. The only accepted correction scope is an existing
reviewed Draft CAP field, and all provenance must remain current.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot

_SAFE_FIELD = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class HumanCorrectionDispositionError(RuntimeError):
    """Evidence, reviewer identity or correction scope is not safe."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _location(snapshot: CandidateQualitySnapshot, report_path: Path) -> Path:
    directory = (
        snapshot.project_root / "Canonical Assets" / snapshot.asset_id / ".metadata" / "evaluation"
    ).resolve(strict=False)
    report = report_path.resolve(strict=True)
    if report.parent != directory or not report.name.endswith(".candidate_quality.json"):
        raise HumanCorrectionDispositionError("Review report is outside CAP evaluation directory")
    if report_path.is_symlink():
        raise HumanCorrectionDispositionError("Symlinked report is not permitted")
    return report.with_name(report.name.removesuffix(".json") + ".human_correction.json")


def _report(snapshot: CandidateQualitySnapshot, path: Path) -> tuple[bytes, dict[str, Any]]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except ValueError as exc:
        raise HumanCorrectionDispositionError("Saved semantic review is not readable") from exc
    if not isinstance(document, dict):
        raise HumanCorrectionDispositionError("Saved semantic review is malformed")
    expected = {
        "schema_version": 1,
        "evaluation_type": "vscs_cap_visual_candidate_quality",
        "governance": "advisory_only_no_approval",
        "asset_id": snapshot.asset_id,
        "reference_id": snapshot.reference_id,
        "reference_role": "supplementary",
        "reference_status": "candidate",
        "image_sha256": snapshot.image_sha256,
        "specification_fingerprint": snapshot.specification_fingerprint,
        "review_fingerprint": snapshot.review_fingerprint,
        "reviewed_fields": dict(snapshot.accepted_fields),
        "decision": "HUMAN_REVIEW_REQUIRED",
    }
    if any(document.get(key) != value for key, value in expected.items()):
        raise HumanCorrectionDispositionError("Review evidence is stale or not eligible")
    semantic = document.get("semantic")
    if not isinstance(semantic, dict) or semantic.get("decision") == "regenerate":
        raise HumanCorrectionDispositionError(
            "A separate, completed advisory semantic review is required"
        )
    return raw, document


def _evidence(
    snapshot: CandidateQualitySnapshot,
    report_path: Path,
    reviewer: str,
    field: str,
    reason: str,
) -> dict[str, Any]:
    reviewer = reviewer.strip()
    reason = reason.strip()
    if not 2 <= len(reviewer) <= 100 or any(ord(char) < 32 for char in reviewer):
        raise HumanCorrectionDispositionError("Reviewer must provide a valid identity")
    if not 15 <= len(reason) <= 2000 or any(ord(char) < 32 for char in reason):
        raise HumanCorrectionDispositionError(
            "Describe a specific visual discrepancy (15-2000 characters)"
        )
    if not _SAFE_FIELD.fullmatch(field) or field not in dict(snapshot.accepted_fields):
        raise HumanCorrectionDispositionError("Correction scope must be one accepted CAP field")
    report_bytes, _ = _report(snapshot, report_path)
    if not snapshot.image_path.is_file() or snapshot.image_path.is_symlink():
        raise HumanCorrectionDispositionError("Original Candidate image is missing or unsafe")
    if _digest(snapshot.image_path.read_bytes()) != snapshot.image_sha256:
        raise HumanCorrectionDispositionError("Candidate image changed since evaluation")
    return {
        "schema_version": 1,
        "kind": "HUMAN_REVIEW_CORRECTION_DISPOSITION",
        "authority": "reviewer_advisory_only_not_semantic_override",
        "asset_id": snapshot.asset_id,
        "reference_id": snapshot.reference_id,
        "source_image_sha256": snapshot.image_sha256,
        "semantic_report_sha256": _digest(report_bytes),
        "specification_fingerprint": snapshot.specification_fingerprint,
        "review_fingerprint": snapshot.review_fingerprint,
        "accepted_field": field,
        "accepted_field_value_sha256": _digest(
            dict(snapshot.accepted_fields)[field].encode("utf-8")
        ),
        "reviewer": reviewer,
        "observed_discrepancy": reason,
        "semantic_decision_overridden": False,
        "candidate_approved": False,
        "provider_execution_authorized": False,
    }


def save_human_correction_disposition(
    snapshot: CandidateQualitySnapshot,
    report_path: Path,
    *,
    reviewer: str,
    accepted_field: str,
    observed_discrepancy: str,
) -> Path:
    """Append one immutable, independently attributable human correction decision."""
    location = _location(snapshot, report_path)
    evidence = _evidence(snapshot, report_path, reviewer, accepted_field, observed_discrepancy)
    payload = {
        **evidence,
        "recorded_utc": datetime.now(UTC).isoformat(),
    }
    try:
        fd = os.open(location, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise HumanCorrectionDispositionError(
            "A disposition already exists for this report; never overwrite a reviewer decision"
        ) from exc
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    return location


def verify_human_correction_disposition(
    snapshot: CandidateQualitySnapshot, report_path: Path
) -> tuple[Path, str, str]:
    """Verify current advisory disposition; return path, checksum and field."""
    location = _location(snapshot, report_path)
    if not location.is_file() or location.is_symlink():
        raise HumanCorrectionDispositionError("No saved human correction decision exists")
    raw = location.read_bytes()
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HumanCorrectionDispositionError("Human correction record is invalid") from exc
    if not isinstance(payload, dict):
        raise HumanCorrectionDispositionError("Human correction record is not an object")
    reviewer = payload.get("reviewer")
    field = payload.get("accepted_field")
    reason = payload.get("observed_discrepancy")
    if (
        not isinstance(reviewer, str)
        or not isinstance(field, str)
        or not isinstance(reason, str)
    ):
        raise HumanCorrectionDispositionError("Human correction record is incomplete")
    evidence = _evidence(snapshot, report_path, reviewer, field, reason)
    if any(payload.get(key) != value for key, value in evidence.items()):
        raise HumanCorrectionDispositionError("Human correction evidence changed or is stale")
    if not isinstance(payload.get("recorded_utc"), str):
        raise HumanCorrectionDispositionError("Human correction record lacks timestamp")
    if set(payload) != set(evidence) | {"recorded_utc"}:
        raise HumanCorrectionDispositionError("Human correction record contains unknown authority")
    return location, _digest(raw), field
