"""Governed offline requalification of unchanged visual-candidate image bytes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from vscs.application.caps.design_revision import REVISION_HISTORY_KEY
from vscs.application.caps.reference_service import CanonicalReferenceService
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.application.caps.visual_identity_preparation import prepare_visual_identity
from vscs.domain.caps import (
    CanonicalReferenceCreate,
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CAPStatus,
)

_PNG = b"\x89PNG\r\n\x1a\n"


class CandidateRequalificationError(ValueError):
    """The candidate cannot safely acquire a new review identity."""


@dataclass(frozen=True)
class CandidateRequalificationPlan:
    asset_id: str
    source_reference_id: int
    image_path: Path
    image_sha256: str
    previous_specification_fingerprint: str
    current_specification_fingerprint: str
    current_review_fingerprint: str
    original_prompt: str
    changed_fields: tuple[str, ...]
    original_manifest: dict[str, object]
    current_prompt: str


class CandidateRequalificationService:
    def __init__(self, references: CanonicalReferenceService) -> None:
        self.references = references

    def prepare(self, asset_id: str, reference_id: int) -> CandidateRequalificationPlan:
        refs = self.references
        cap = refs.caps.get(asset_id)
        if cap.status is not CAPStatus.DRAFT:
            raise CandidateRequalificationError("Only reviewed Draft CAPs can be requalified")
        reference = refs.get(reference_id)
        if (
            reference.cap_id != cap.id
            or reference.reference_type is not CanonicalReferenceType.IMAGE
            or reference.role is not CanonicalReferenceRole.SUPPLEMENTARY
            or reference.status is not CanonicalReferenceStatus.CANDIDATE
            or reference.locked
        ):
            raise CandidateRequalificationError("Select an unlocked local Image Candidate")
        project = refs.caps.assets.projects.project_directory
        if project is None:
            raise CandidateRequalificationError("Open a VSCS project")
        project = project.resolve(strict=False)
        image = (project / reference.file_path).resolve(strict=False)
        expected = Path("Canonical Assets") / asset_id / "Images" / "Visual Candidates"
        try:
            if image.relative_to(project).parent != expected:
                raise CandidateRequalificationError("Not a managed local Visual Candidate")
        except ValueError as exc:
            raise CandidateRequalificationError("Candidate path escapes the project") from exc
        if not image.is_file():
            raise CandidateRequalificationError("Original image is missing")
        content = image.read_bytes()
        if not content.startswith(_PNG):
            raise CandidateRequalificationError("Original image is not a PNG")
        digest = hashlib.sha256(content).hexdigest()
        manifest_path = (
            project / "Canonical Assets" / asset_id / ".metadata" / "visual" / f"{image.stem}.json"
        )
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            history = json.loads(cap.production_metadata[REVISION_HISTORY_KEY])
        except (OSError, KeyError, ValueError) as exc:
            raise CandidateRequalificationError(
                "Original provenance or revision history missing"
            ) from exc
        if not isinstance(manifest, dict) or not isinstance(history, list) or not history:
            raise CandidateRequalificationError("Malformed provenance or revision history")
        if (
            manifest.get("asset_id") != asset_id
            or manifest.get("image_sha256") != digest
            or manifest.get("prompt") != reference.description
            or manifest.get("governance") != "non-authoritative_candidate_not_MASTER"
        ):
            raise CandidateRequalificationError("Original Candidate provenance is inconsistent")
        # Requalification of already requalified candidates must be separately
        # designed; never use a derived manifest as original generation evidence.
        if "requalification" in manifest or "regeneration" in manifest:
            raise CandidateRequalificationError("Only original local Candidates qualify")
        matching: dict[str, object] | None = None
        for entry in history:
            if not isinstance(entry, dict):
                raise CandidateRequalificationError("Malformed review revision record")
            old_spec = entry.get("previous_specification")
            old_audit = entry.get("previous_review_audit")
            if not isinstance(old_spec, dict) or not isinstance(old_audit, dict):
                raise CandidateRequalificationError("Review history lacks original evidence")
            try:
                historical_fingerprint = CAPStructuredSpecification.model_validate(
                    old_spec
                ).fingerprint()
            except ValueError as exc:
                raise CandidateRequalificationError("Invalid historical CAP specification") from exc
            historical_review_fingerprint = hashlib.sha256(
                json.dumps(old_audit, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            if (
                manifest.get("specification_fingerprint") == historical_fingerprint
                and manifest.get("review_fingerprint") == historical_review_fingerprint
            ):
                matching = entry
                break
        if matching is None:
            raise CandidateRequalificationError(
                "Original manifest is not supported by saved design-revision history"
            )
        preparation = prepare_visual_identity(cap, ())
        if not preparation.ready_for_master_candidate:
            raise CandidateRequalificationError(
                "Current CAP cannot prepare a candidate: " + "; ".join(preparation.blockers)
            )
        if manifest.get("specification_fingerprint") == preparation.specification_fingerprint:
            raise CandidateRequalificationError(
                "Candidate already matches the current reviewed CAP"
            )
        changed = tuple(
            dict.fromkeys(
                str(item.get("field"))
                for item in history
                if isinstance(item, dict) and item.get("field")
            )
        )
        return CandidateRequalificationPlan(
            asset_id=asset_id,
            source_reference_id=reference_id,
            image_path=image,
            image_sha256=digest,
            previous_specification_fingerprint=str(manifest["specification_fingerprint"]),
            current_specification_fingerprint=preparation.specification_fingerprint,
            current_review_fingerprint=preparation.review_fingerprint,
            original_prompt=reference.description,
            changed_fields=changed,
            original_manifest=manifest,
            current_prompt=preparation.master_candidate_prompt,
        )

    def accept(self, plan: CandidateRequalificationPlan, reviewer: str, rationale: str) -> int:
        reviewer, rationale = reviewer.strip(), rationale.strip()
        if not reviewer or len(rationale) < 15:
            raise CandidateRequalificationError(
                "Reviewer and rationale (15+ characters) are required"
            )
        if self.prepare(plan.asset_id, plan.source_reference_id) != plan:
            raise CandidateRequalificationError("Candidate or reviewed CAP changed; inspect again")
        project = self.references.caps.assets.projects.project_directory
        if project is None:
            raise CandidateRequalificationError("Project closed")
        project = project.resolve(strict=False)
        cap = self.references.caps.get(plan.asset_id)
        filename = f"{cap.asset_id}_visual_{uuid4().hex}.png"
        destination = plan.image_path.parent / filename
        manifest = (
            project
            / "Canonical Assets"
            / cap.asset_id
            / ".metadata"
            / "visual"
            / f"{destination.stem}.json"
        )
        # The evaluation prompt is explicitly a new review context, not the
        # historical generation prompt. Both are kept in the manifest.
        prompt = (
            "OFFLINE REQUALIFICATION (not a new image generation). "
            f"Current reviewed design: {plan.current_prompt} "
            "The image bytes were reused from an earlier Candidate."
        )
        payload = {
            "asset_id": plan.asset_id,
            "image_sha256": plan.image_sha256,
            "specification_fingerprint": plan.current_specification_fingerprint,
            "review_fingerprint": plan.current_review_fingerprint,
            "governance": "non-authoritative_candidate_not_MASTER",
            "prompt": prompt,
            "provider": "offline_existing_image_requalification_no_generation",
            "requalification": {
                "source_reference_id": plan.source_reference_id,
                "source_image_sha256": plan.image_sha256,
                "original_generation_prompt": plan.original_prompt,
                "original_specification_fingerprint": plan.previous_specification_fingerprint,
                "reviewer": reviewer,
                "rationale": rationale,
                "source_manifest": plan.original_manifest,
                "no_image_generation": True,
                "not_canonical_approval": True,
            },
        }
        reference_id: int | None = None
        try:
            destination.write_bytes(plan.image_path.read_bytes())
            manifest.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            reference = self.references.create(
                plan.asset_id,
                CanonicalReferenceCreate(
                    cap_id=cap.id,
                    reference_type=CanonicalReferenceType.IMAGE,
                    role=CanonicalReferenceRole.SUPPLEMENTARY,
                    title=f"{cap.title} — requalified visual candidate",
                    file_path=destination.relative_to(project),
                    description=prompt,
                    notes=(
                        f"Offline human requalification by {reviewer}. "
                        f"Source Candidate #{plan.source_reference_id}; no generation, no MASTER approval. "
                        f"Manifest: {manifest.relative_to(project)}"
                    ),
                    version=cap.version,
                ),
            )
            reference_id = reference.id
            self.references.mark_candidate(reference_id)
        except Exception:
            if reference_id is not None:
                self.references.delete(reference_id)
            destination.unlink(missing_ok=True)
            manifest.unlink(missing_ok=True)
            raise
        return reference_id
