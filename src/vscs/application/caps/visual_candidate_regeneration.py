"""B.5.26D: evidence-grounded, bounded correction of a local image Candidate.

Never consume free-form evaluator text as new canonical design. Only reviewed CAP
attributes may drive constraints. One human-confirmed local generation per call.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.visual_candidate_generation import VisualCandidateGenerationService
from vscs.application.caps.visual_candidate_quality import (
    CandidateQualityReviewService,
    CandidateQualitySnapshot,
)
from vscs.application.caps.visual_identity_preparation import VisualIdentityPreparation
from vscs.domain.caps import CanonicalAssetGenerationRequest

MAX_CORRECTION_ATTEMPTS = 2


class CandidateRegenerationError(RuntimeError):
    """Corrective generation cannot proceed without trustworthy current evidence."""


@dataclass(frozen=True, slots=True)
class CandidateRegenerationPlan:
    preparation: VisualIdentityPreparation
    source: CandidateQualitySnapshot
    report_path: Path
    report_sha256: str
    original_reference_id: int
    attempt: int
    max_attempts: int
    request: CanonicalAssetGenerationRequest
    correction_rules: tuple[str, ...]
    review_findings: tuple[str, ...]
    previous_technical_score: int
    previous_semantic_score: int

    @property
    def lineage(self) -> dict[str, str | int]:
        return {
            "original_reference_id": self.original_reference_id,
            "parent_reference_id": self.source.reference_id,
            "attempt": self.attempt,
            "source_quality_report": str(
                self.report_path.relative_to(self.source.project_root)
            ),
            "source_quality_report_sha256": self.report_sha256,
            "source_image_sha256": self.source.image_sha256,
            "previous_technical_score": self.previous_technical_score,
            "previous_semantic_score": self.previous_semantic_score,
        }


class CandidateRegenerationService:
    """Prepare, validate and count correction attempts in the existing CAP project."""

    def __init__(self, references: CanonicalReferenceService) -> None:
        self.quality = CandidateQualityReviewService(references)
        self.generator = VisualCandidateGenerationService(references)

    @staticmethod
    def _manifest_path(snapshot: CandidateQualitySnapshot) -> Path:
        return (
            snapshot.project_root
            / "Canonical Assets"
            / snapshot.asset_id
            / ".metadata"
            / "visual"
            / f"{snapshot.image_path.stem}.json"
        )

    def _lineage(self, snapshot: CandidateQualitySnapshot) -> tuple[int, int]:
        try:
            payload = json.loads(self._manifest_path(snapshot).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CandidateRegenerationError("Candidate generation manifest missing") from exc
        history = payload.get("regeneration")
        if history is None:
            return snapshot.reference_id, 0
        if not isinstance(history, dict):
            raise CandidateRegenerationError("Candidate regeneration lineage is malformed")
        root = history.get("original_reference_id")
        attempt = history.get("attempt")
        if (
            type(root) is not int
            or root < 1
            or type(attempt) is not int
            or not 1 <= attempt <= MAX_CORRECTION_ATTEMPTS
        ):
            raise CandidateRegenerationError("Invalid Candidate correction lineage")
        return root, attempt

    @staticmethod
    def _count_attempts(snapshot: CandidateQualitySnapshot, root: int) -> int:
        directory = (
            snapshot.project_root
            / "Canonical Assets"
            / snapshot.asset_id
            / ".metadata"
            / "visual"
        )
        count = 0
        for path in directory.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CandidateRegenerationError(
                    "Cannot safely count historical visual Candidate attempts"
                ) from exc
            if not isinstance(data, dict):
                raise CandidateRegenerationError("Malformed historical Candidate manifest")
            history = data.get("regeneration")
            if not isinstance(history, dict):
                continue
            if history.get("original_reference_id") == root:
                count += 1
        return count

    def latest_semantic_report(self, asset_id: str, reference_id: int) -> Path:
        """Find the latest saved semantic review without a new paid API call."""
        snapshot = self.quality.snapshot(asset_id, reference_id)
        audit_dir = (
            snapshot.project_root / "Canonical Assets" / asset_id / ".metadata"
            / "evaluation"
        )
        pattern = f"{snapshot.image_path.stem}.*.candidate_quality.json"
        candidates = sorted(
            audit_dir.glob(pattern),
            key=lambda item: item.stat().st_mtime_ns,
            reverse=True,
        )
        for candidate in candidates:
            try:
                payload = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise CandidateRegenerationError(
                    "Saved semantic audit cannot be read safely"
                ) from exc
            if not isinstance(payload, dict):
                raise CandidateRegenerationError("Malformed saved quality audit")
            if (
                payload.get("reference_id") == reference_id
                and payload.get("asset_id") == asset_id
                and isinstance(payload.get("semantic"), dict)
            ):
                return candidate
        raise CandidateRegenerationError(
            "No saved semantic Candidate review found. "
            "Run Review Visual Candidate with explicit semantic consent first."
        )

    def prepare(
        self, asset_id: str, reference_id: int, report_path: Path
    ) -> CandidateRegenerationPlan:
        snapshot = self.quality.snapshot(asset_id, reference_id)
        project_root = snapshot.project_root
        path = report_path.resolve(strict=False)
        directory = (
            project_root / "Canonical Assets" / asset_id / ".metadata" / "evaluation"
        ).resolve(strict=False)
        if path.parent != directory or not path.name.endswith(".candidate_quality.json"):
            raise CandidateRegenerationError(
                "Review report is outside governed CAP audit directory"
            )
        try:
            report_bytes = path.read_bytes()
            data = json.loads(report_bytes)
        except (OSError, ValueError) as exc:
            raise CandidateRegenerationError("Saved Candidate quality report is invalid") from exc
        if not isinstance(data, dict):
            raise CandidateRegenerationError("Review report must be a JSON object")
        for field, expected in (
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
        ):
            if data.get(field) != expected:
                raise CandidateRegenerationError(
                    f"Saved report {field} disagrees with current Candidate authority"
                )
        if data.get("reviewed_fields") != dict(snapshot.accepted_fields):
            raise CandidateRegenerationError("Reviewed fields changed since image evaluation")
        if data.get("decision") != "REGENERATE_RECOMMENDED":
            raise CandidateRegenerationError("Regeneration requires a recorded review failure")
        semantic = data.get("semantic")
        if not isinstance(semantic, dict) or semantic.get("decision") != "regenerate":
            raise CandidateRegenerationError(
                "Controlled correction requires a failed semantic review, "
                "not technical scores alone"
            )
        overall = semantic.get("overall_score")
        if type(overall) is not int or not 0 <= overall <= 100:
            raise CandidateRegenerationError("Missing semantic review score")
        technical = data.get("technical")
        if not isinstance(technical, dict):
            raise CandidateRegenerationError("Missing technical quality evidence")
        technical_score = technical.get("overall_score")
        if type(technical_score) is not int or not 0 <= technical_score <= 100:
            raise CandidateRegenerationError("Missing technical review score")
        current = self.generator.prepare(asset_id)
        if not current.ready_for_master_candidate:
            raise CandidateRegenerationError(
                "Current CAP visual identity is not ready; resolve governed design first"
            )
        if (
            current.specification_fingerprint != snapshot.specification_fingerprint
            or current.review_fingerprint != snapshot.review_fingerprint
        ):
            raise CandidateRegenerationError("Source CAP changed since quality review")
        root, parent_attempt = self._lineage(snapshot)
        count = self._count_attempts(snapshot, root)
        attempt = max(count, parent_attempt) + 1
        if attempt > MAX_CORRECTION_ATTEMPTS:
            raise CandidateRegenerationError(
                f"Correction limit reached ({MAX_CORRECTION_ATTEMPTS} local attempts per original)"
            )
        # Free-form semantic text is displayed to the operator only, never put
        # into the provider prompt as if it were approved canonical evidence.
        findings = semantic.get("violations", [])
        if not isinstance(findings, list) or not all(
            isinstance(item, str) for item in findings
        ):
            raise CandidateRegenerationError("Malformed semantic evidence")
        corrections = tuple(
            f"MANDATORY reviewed {field}: {value}"
            for field, value in snapshot.accepted_fields
        )
        if not corrections:
            raise CandidateRegenerationError("No accepted design exists to ground corrections")
        negative = current.negative_prompt
        prompt = (
            current.master_candidate_prompt
            + "\nCONTROLLED B.5.26D CORRECTION — only reviewed Draft details below "
            "are authoritative for this new candidate. Previous image is rejected "
            "as a visual match; do not replicate its unreviewed details. "
            "Follow each mandatory field literally. "
            + " ".join(corrections)
            + " Do not introduce extra doors, equipment, markings, fixtures or lighting "
            "beyond the reviewed design; deferred features remain undecided. "
            "Show a complete, coherent reference composition. "
            "This is a visual proposal only, not Canon or MASTER."
        )
        # Explicitly change seed to avoid silently repeating identical output.
        manifest = json.loads(self._manifest_path(snapshot).read_text(encoding="utf-8"))
        old_seed = manifest.get("seed")
        seed = old_seed + attempt if type(old_seed) is int and old_seed >= 0 else attempt
        old_width = manifest.get("width")
        old_height = manifest.get("height")
        width = old_width if type(old_width) is int and 256 <= old_width <= 8192 else 1280
        height = old_height if type(old_height) is int and 256 <= old_height <= 8192 else 720
        project, base = self.generator.prepare_request(
            current, seed=seed, width=width, height=height
        )
        if project != project_root:
            raise CandidateRegenerationError("Project switched while preparing correction")
        request = base.model_copy(
            update={"prompt": prompt, "negative_prompt": negative}
        )
        return CandidateRegenerationPlan(
            preparation=current,
            source=snapshot,
            report_path=path,
            report_sha256=hashlib.sha256(report_bytes).hexdigest(),
            original_reference_id=root,
            attempt=attempt,
            max_attempts=MAX_CORRECTION_ATTEMPTS,
            request=request,
            correction_rules=corrections,
            review_findings=tuple(findings),
            previous_technical_score=technical_score,
            previous_semantic_score=overall,
        )

    def verify_current(self, plan: CandidateRegenerationPlan) -> None:
        current = self.prepare(
            plan.source.asset_id, plan.source.reference_id, plan.report_path
        )
        if current != plan:
            raise CandidateRegenerationError(
                "Source evaluation, attempt budget, CAP or Candidate changed during generation"
            )
