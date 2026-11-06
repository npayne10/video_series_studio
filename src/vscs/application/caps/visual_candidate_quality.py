"""B.5.26: source-grounded, non-authoritative quality review for local CAP images.

Combines existing CIEE technical checks and optional existing SIEE vision checks.
A report never approves, rejects, promotes or regenerates a canonical reference.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.visual_identity_preparation import prepare_visual_identity
from vscs.application.ciee import CanonicalImageEvaluationEngine
from vscs.application.ciee.models import CanonicalImageEvaluation
from vscs.application.siee import SemanticImageEvaluationEngine
from vscs.application.siee.models import SemanticImageEvaluation
from vscs.application.siee.provider import SemanticEvaluationProvider
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)


class CandidateQualityError(RuntimeError):
    """Raised when the selected Candidate or its evidence cannot be trusted."""


@dataclass(frozen=True, slots=True)
class CandidateQualitySnapshot:
    asset_id: str
    asset_name: str
    category: AssetCategory
    reference_id: int
    project_root: Path
    image_path: Path
    image_sha256: str
    specification_fingerprint: str
    review_fingerprint: str
    accepted_fields: tuple[tuple[str, str], ...]
    deferred_fields: tuple[str, ...]
    continuity: tuple[str, ...]
    dependencies: tuple[str, ...]
    generation_prompt: str
    reference_role: str
    reference_status: str


@dataclass(frozen=True, slots=True)
class CandidateQualityResult:
    snapshot: CandidateQualitySnapshot
    technical: CanonicalImageEvaluation
    semantic: SemanticImageEvaluation | None
    recommendations: tuple[str, ...]

    @property
    def decision(self) -> str:
        if self.technical.decision.value == "regenerate":
            return "REGENERATE_RECOMMENDED"
        if self.semantic is None:
            return "SEMANTIC_REVIEW_NOT_RUN"
        if self.semantic.decision.value == "regenerate":
            return "REGENERATE_RECOMMENDED"
        # Even a provider PASS is advisory, not a human approval.
        return "HUMAN_REVIEW_REQUIRED"

    def as_dict(self) -> dict[str, object]:
        snap = self.snapshot
        return {
            "schema_version": 1,
            "evaluation_type": "vscs_cap_visual_candidate_quality",
            "governance": "advisory_only_no_approval",
            "asset_id": snap.asset_id,
            "reference_id": snap.reference_id,
            "reference_role": snap.reference_role,
            "reference_status": snap.reference_status,
            "image": str(snap.image_path.relative_to(snap.project_root)),
            "image_sha256": snap.image_sha256,
            "specification_fingerprint": snap.specification_fingerprint,
            "review_fingerprint": snap.review_fingerprint,
            "reviewed_fields": dict(snap.accepted_fields),
            "deferred_fields": list(snap.deferred_fields),
            "continuity": list(snap.continuity),
            "related_asset_ids": list(snap.dependencies),
            "decision": self.decision,
            "technical": self.technical.as_dict(),
            "semantic": self.semantic.as_dict() if self.semantic else None,
            "recommendations": list(self.recommendations),
        }


class CandidateQualityReviewService:
    """Read-only source preflight, image checks and immutable report persistence."""

    def __init__(self, references: CanonicalReferenceService) -> None:
        self.references = references

    def snapshot(self, asset_id: str, reference_id: int) -> CandidateQualitySnapshot:
        refs = self.references
        project = refs.caps.assets.projects.project_directory
        if project is None:
            raise CandidateQualityError("Open the VSCS project before evaluating candidates")
        root = project.resolve(strict=False)
        cap = refs.caps.get(asset_id)
        asset = refs.caps.assets.get(asset_id)
        reference = refs.get(reference_id)
        if reference.cap_id != cap.id:
            raise CandidateQualityError("Selected reference does not belong to the CAP")
        if (
            reference.reference_type is not CanonicalReferenceType.IMAGE
            or reference.role is not CanonicalReferenceRole.SUPPLEMENTARY
            or reference.status is not CanonicalReferenceStatus.CANDIDATE
            or reference.locked
        ):
            raise CandidateQualityError(
                "Select an unlocked supplementary Image Candidate; this review does not approve it"
            )
        image_path = (root / reference.file_path).resolve(strict=False)
        try:
            relative = image_path.relative_to(root)
        except ValueError as exc:
            raise CandidateQualityError("Candidate image lies outside the VSCS project") from exc
        expected_prefix = Path("Canonical Assets") / asset_id / "Images" / "Visual Candidates"
        if relative.parent != expected_prefix:
            raise CandidateQualityError(
                "This workflow evaluates B.5.26 local Visual Candidates only"
            )
        if not image_path.is_file():
            raise CandidateQualityError("Selected Candidate image is missing")
        image_digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        preparation = prepare_visual_identity(cap, (), ())
        if not preparation.specification_fingerprint or not preparation.review_fingerprint:
            raise CandidateQualityError("Candidate CAP lacks verified reviewed design authority")
        if preparation.category != asset.category:
            raise CandidateQualityError("Reviewed CAP category differs from registered asset")
        if any("Reviewed specification is not verifiable" in s for s in preparation.blockers):
            raise CandidateQualityError("CAP review provenance is invalid")

        manifest_path = (
            root / "Canonical Assets" / asset_id / ".metadata" / "visual"
            / f"{image_path.stem}.json"
        )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CandidateQualityError(
                "Local candidate provenance manifest is unavailable"
            ) from exc
        if not isinstance(manifest, dict) or any(
            manifest.get(key) != expected
            for key, expected in (
                ("asset_id", asset_id),
                ("image_sha256", image_digest),
                ("specification_fingerprint", preparation.specification_fingerprint),
                ("review_fingerprint", preparation.review_fingerprint),
                ("governance", "non-authoritative_candidate_not_MASTER"),
            )
        ):
            raise CandidateQualityError(
                "Candidate image or its reviewed CAP provenance has changed; "
                "a new Candidate is required"
            )
        prompt = manifest.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or prompt != reference.description:
            raise CandidateQualityError("Candidate generation prompt provenance mismatch")
        return CandidateQualitySnapshot(
            asset_id=asset_id,
            asset_name=asset.name,
            category=asset.category,
            reference_id=reference_id,
            project_root=root,
            image_path=image_path,
            image_sha256=image_digest,
            specification_fingerprint=preparation.specification_fingerprint,
            review_fingerprint=preparation.review_fingerprint,
            accepted_fields=preparation.accepted_fields,
            deferred_fields=preparation.deferred_fields,
            continuity=preparation.continuity_context,
            dependencies=preparation.dependency_asset_ids,
            generation_prompt=prompt,
            reference_role=reference.role.value,
            reference_status=reference.status.value,
        )

    def evaluate(
        self,
        snapshot: CandidateQualitySnapshot,
        *,
        semantic_provider: SemanticEvaluationProvider | None = None,
    ) -> CandidateQualityResult:
        technical = CanonicalImageEvaluationEngine().evaluate(
            snapshot.image_path, asset_id=snapshot.asset_id, category=snapshot.category
        )
        semantic: SemanticImageEvaluation | None = None
        if semantic_provider is not None:
            accepted = "\n".join(f"- {key}: {value}" for key, value in snapshot.accepted_fields)
            deferred = ", ".join(snapshot.deferred_fields) or "(none)"
            continuity = "\n".join(snapshot.continuity) or "(none)"
            dependencies = ", ".join(snapshot.dependencies) or "(no reviewed IDs)"
            notes = (
                "This is reviewed DRAFT design, NOT established Story Canon. "
                "Evaluate the image against ONLY the accepted design details; "
                "do not treat the image as authority for new features. "
                "Indicate contradictions and visible unreviewed features in violations, "
                "with evidence and actionable recommendations. "
                "Avoid claiming that a single image verifies physical measurements. "
                f"Accepted Draft fields:\n{accepted}\n"
                f"Deferred/unapproved details (do not assume fixed): {deferred}\n"
                f"Cross-asset continuity context:\n{continuity}\n"
                f"Related governed IDs: {dependencies}. "
                "If a separate console/workstation appears, distinguish placement "
                "from unverified appearance. No approved primary reference exists."
            )
            semantic = SemanticImageEvaluationEngine(semantic_provider).evaluate(
                snapshot.image_path,
                asset_id=snapshot.asset_id,
                asset_name=snapshot.asset_name,
                category=snapshot.category,
                canonical_description=notes,
                visual_identity="; ".join(
                    f"{key}: {value}" for key, value in snapshot.accepted_fields
                ),
                production_notes=notes,
                generation_prompt=snapshot.generation_prompt,
            )
        recommendations: list[str] = list(technical.manual_checks)
        recommendations.extend(technical.warnings)
        if semantic is None:
            recommendations.insert(
                0,
                "Technical inspection cannot identify objects or compare visual "
                "details with CAP design. Run the separately consented semantic "
                "evaluation or inspect the Candidate manually before any decision.",
            )
        else:
            recommendations.extend(semantic.violations)
            recommendations.extend(semantic.recommendations)
        if snapshot.deferred_fields:
            recommendations.append(
                "Do not promote unresolved Draft details to Canon: "
                + ", ".join(snapshot.deferred_fields)
            )
        return CandidateQualityResult(
            snapshot=snapshot,
            technical=technical,
            semantic=semantic,
            recommendations=tuple(dict.fromkeys(recommendations)),
        )

    def save(self, result: CandidateQualityResult) -> Path:
        current = self.snapshot(result.snapshot.asset_id, result.snapshot.reference_id)
        if current != result.snapshot:
            raise CandidateQualityError(
                "Image, CAP review, or reference authority changed during evaluation; "
                "discarding stale review"
            )
        snapshot = result.snapshot
        report_id = uuid4().hex
        target = (
            snapshot.project_root
            / "Canonical Assets"
            / snapshot.asset_id
            / ".metadata"
            / "evaluation"
            / f"{snapshot.image_path.stem}.{report_id}.candidate_quality.json"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = result.as_dict()
        payload["evaluated_at"] = datetime.now(UTC).isoformat()
        payload["report_id"] = report_id
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(target)
        return target
