"""F5.4.2 C2.1: immutable, source-bound saved human-review sessions.

Persistence never confers ROI approval, generation, CAP authority or mask
provider compatibility. Loading replays every field through Stage B validation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from vscs.application.caps.general_visual_correction_triage import VisualCorrectionTriage
from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError, GeometryDefect
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
    prepare_governed_correction_proposal,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    SpatialEvidenceReview,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot

_HEX = re.compile(r"^[0-9a-f]{64}$")
_MAX_RECORD_BYTES = 96_000


@dataclass(frozen=True, slots=True)
class SavedHumanReview:
    path: Path
    review: SpatialEvidenceReview
    proposal_sha256: str | None
    saved_utc: str


@dataclass(frozen=True, slots=True)
class ExistingMaskVersion:
    path: Path
    sha256: str
    source_size: tuple[int, int]
    white_pixel_count: int
    proposal_prefix: str
    matches_current_proposal: bool

    def describe(self) -> str:
        status = (
            "Matches current C1 proposal"
            if self.matches_current_proposal
            else "Historical mask only; NOT bound to current C1 proposal"
        )
        return (
            f"{self.path.name}: {self.white_pixel_count} proposed editable pixels; "
            f"SHA-256 {self.sha256}; {status}"
        )


def _check_current_source(snapshot: CandidateQualitySnapshot) -> None:
    """Reject stale in-dialog snapshots before any read or persistence."""
    if (
        snapshot.image_path.is_symlink()
        or not snapshot.image_path.is_file()
        or not _HEX.fullmatch(snapshot.image_sha256)
    ):
        raise GeometryCorrectionError("Candidate source is missing or unsafe")
    try:
        digest = hashlib.sha256(snapshot.image_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise GeometryCorrectionError("Cannot recheck Candidate source") from exc
    if digest != snapshot.image_sha256:
        raise GeometryCorrectionError("Candidate source changed since quality review")


def _session_directory(snapshot: CandidateQualitySnapshot) -> Path:
    return (
        snapshot.project_root
        / "Canonical Assets"
        / snapshot.asset_id
        / ".metadata"
        / "human_visual_reviews"
    )


def _safe_directory(root: Path, *, create: bool) -> Path:
    if root.is_symlink() or root.parent.is_symlink() or not root.parent.is_dir():
        raise GeometryCorrectionError("Canonical review metadata directory is unavailable")
    if create and not root.exists():
        root.mkdir()
    if not root.is_dir() or root.is_symlink() or root.resolve(strict=True) != root:
        raise GeometryCorrectionError("Review directory is not a safe canonical directory")
    return root


def _hash(payload: dict[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _identity(snapshot: CandidateQualitySnapshot) -> dict[str, object]:
    return {
        "asset_id": snapshot.asset_id,
        "reference_id": snapshot.reference_id,
        "source_sha256": snapshot.image_sha256,
        "specification_fingerprint": snapshot.specification_fingerprint,
        "review_fingerprint": snapshot.review_fingerprint,
        "accepted_fields": list(snapshot.accepted_fields),
        "reference_role": snapshot.reference_role,
        "reference_status": snapshot.reference_status,
    }


def _payload(
    snapshot: CandidateQualitySnapshot,
    review: SpatialEvidenceReview,
    proposal: GovernedCorrectionProposal | None,
) -> dict[str, object]:
    if (
        review.asset_id != snapshot.asset_id
        or review.reference_id != snapshot.reference_id
        or review.source_sha256 != snapshot.image_sha256
        or tuple((item.field, item.requirement) for item in review.reviewed_fields)
        != snapshot.accepted_fields
        or any(
            (
                review.gpu_execution_authorized,
                review.cap_registration_allowed,
                review.canon_approval_allowed,
                review.governed_attempt_allowed,
            )
        )
    ):
        raise GeometryCorrectionError("Cannot save a stale or authoritative human review")
    if proposal is not None:
        proposal.verify_seal()
        expected = prepare_governed_correction_proposal(
            review,
            target_field=proposal.target_field,
            expected_source_sha256=snapshot.image_sha256,
            reviewer_confirmed_roi=True,
        )
        if proposal != expected:
            raise GeometryCorrectionError("C1 provenance is not bound to these reviewed fields")
    fields: list[dict[str, object]] = []
    for item in review.reviewed_fields:
        roi = item.proposed_region
        fields.append(
            {
                "field": item.field,
                "requirement": item.requirement,
                "status": item.status.value,
                "observation": item.observation,
                "defect": item.defect.value if item.defect is not None else None,
                "roi": [roi.x, roi.y, roi.width, roi.height] if roi is not None else None,
            }
        )
    return {
        "schema_version": 1,
        "identity": _identity(snapshot),
        "fields": fields,
        "c1_proposal_sha256": proposal.proposal_sha256 if proposal is not None else None,
        "saved_utc": datetime.now(UTC).isoformat(),
        "no_authority": True,
    }


def save_human_review_session(
    snapshot: CandidateQualitySnapshot,
    review: SpatialEvidenceReview,
    *,
    proposal: GovernedCorrectionProposal | None = None,
) -> Path:
    """Create a new immutable JSON record; never replace previous review evidence."""
    _check_current_source(snapshot)
    data = _payload(snapshot, review, proposal)
    sealed = {"payload": data, "sha256": _hash(data)}
    raw = (json.dumps(sealed, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if len(raw) > _MAX_RECORD_BYTES:
        raise GeometryCorrectionError("Human review record exceeds maximum size")
    target = _safe_directory(_session_directory(snapshot), create=True)
    name = f"c21-{snapshot.reference_id}-{uuid4().hex}.json"
    path = target / name
    try:
        with path.open("xb") as out:
            out.write(raw)
    except OSError as exc:
        raise GeometryCorrectionError("Could not save human-review evidence") from exc
    return path


def list_human_review_sessions(snapshot: CandidateQualitySnapshot) -> tuple[Path, ...]:
    directory = _session_directory(snapshot)
    if not directory.exists():
        return ()
    _safe_directory(directory, create=False)
    candidates = []
    for p in directory.glob(f"c21-{snapshot.reference_id}-*.json"):
        if p.is_symlink() or not p.is_file():
            raise GeometryCorrectionError("Unsafe saved review session path")
        candidates.append(p)
    return tuple(sorted(candidates, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True))


def load_human_review_session(
    snapshot: CandidateQualitySnapshot,
    triage: VisualCorrectionTriage,
    *,
    path: Path,
) -> SavedHumanReview:
    _check_current_source(snapshot)
    directory = _safe_directory(_session_directory(snapshot), create=False)
    if (
        path.parent != directory
        or not re.fullmatch(rf"c21-{snapshot.reference_id}-[0-9a-f]{{32}}\.json", path.name)
        or path.is_symlink()
        or not path.is_file()
        or path.stat().st_size > _MAX_RECORD_BYTES
    ):
        raise GeometryCorrectionError("Saved human-review path is invalid")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GeometryCorrectionError("Saved human-review record cannot be read") from exc
    if (
        not isinstance(record, dict)
        or not isinstance(record.get("payload"), dict)
        or record.get("sha256") != _hash(record["payload"])
    ):
        raise GeometryCorrectionError("Saved human-review record seal is invalid")
    data = record["payload"]
    if (
        data.get("schema_version") != 1
        or data.get("identity") != _identity(snapshot)
        or data.get("no_authority") is not True
        or not isinstance(data.get("saved_utc"), str)
        or not isinstance(data.get("fields"), list)
        or len(data["fields"]) != len(triage.mandatory_checks)
        or triage.asset_id != snapshot.asset_id
        or triage.reference_id != snapshot.reference_id
        or triage.image_sha256 != snapshot.image_sha256
    ):
        raise GeometryCorrectionError("Saved review is stale or has invalid provenance")
    review: SpatialEvidenceReview | None = None
    try:
        for check, item in zip(triage.mandatory_checks, data["fields"], strict=True):
            if (
                not isinstance(item, dict)
                or item.get("field") != check.field
                or item.get("requirement") != check.requirement
            ):
                raise GeometryCorrectionError("Saved review CAP field order changed")
            defect = item.get("defect")
            roi = item.get("roi")
            if roi is not None and (not isinstance(roi, list) or len(roi) != 4):
                raise GeometryCorrectionError("Saved human-review ROI invalid")
            review = propose_spatial_evidence(
                triage,
                field=check.field,
                status=VisualEvidenceStatus(item["status"]),
                observation=item["observation"],
                defect=GeometryDefect(defect) if defect is not None else None,
                region=NormalizedRegion(*roi) if roi is not None else None,
                expected_source_sha256=snapshot.image_sha256,
                previous=review,
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise GeometryCorrectionError("Saved human-review fields are invalid") from exc
    if review is None:
        raise GeometryCorrectionError("Saved human review is empty")
    proposal_hash = data.get("c1_proposal_sha256")
    if proposal_hash is not None and (
        not isinstance(proposal_hash, str) or not _HEX.fullmatch(proposal_hash)
    ):
        raise GeometryCorrectionError("Saved C1 provenance digest invalid")
    return SavedHumanReview(path, review, proposal_hash, data["saved_utc"])


def list_existing_mask_versions(
    snapshot: CandidateQualitySnapshot,
    *,
    proposal: GovernedCorrectionProposal,
) -> tuple[ExistingMaskVersion, ...]:
    """List all inspected versions, marking exact current-proposal matches.

    Historical masks have unknown source/ROI provenance and remain inspection-only.
    No mask is ever automatically selected or authorized for a provider.
    """
    _check_current_source(snapshot)
    proposal.verify_seal()
    if (
        proposal.asset_id != snapshot.asset_id
        or proposal.source_reference_id != snapshot.reference_id
        or proposal.source_sha256 != snapshot.image_sha256
    ):
        raise GeometryCorrectionError("Mask list proposal does not match source")
    directory = (
        snapshot.project_root
        / "Canonical Assets"
        / snapshot.asset_id
        / ".metadata"
        / "spatial_masks"
    )
    if not directory.exists():
        return ()
    _safe_directory(directory, create=False)
    from vscs.application.caps.human_reviewed_mask_evidence import (
        prepare_reviewed_mask,
    )

    expected = prepare_reviewed_mask(
        proposal,
        source_path=snapshot.image_path,
        reviewer_confirmed_mask=True,
    )
    versions: list[ExistingMaskVersion] = []
    prefix = f"c2-{snapshot.reference_id}-{proposal.proposal_sha256[:16]}-"
    for p in directory.glob(f"c2-{snapshot.reference_id}-*.png"):
        if p.is_symlink() or not p.is_file():
            raise GeometryCorrectionError("Unsafe stored mask path")
        match = re.fullmatch(
            rf"c2-{snapshot.reference_id}-([0-9a-f]{{16}})-([0-9a-f]{{16}})\\.png",
            p.name,
        )
        if match is None:
            raise GeometryCorrectionError("Stored mask filename is invalid")
        if p.stat().st_size > 32_000_000:
            raise GeometryCorrectionError("Stored mask exceeds safe size")
        raw = p.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if match.group(2) != digest[:16]:
            raise GeometryCorrectionError("Stored mask evidence digest mismatch")
        try:
            with Image.open(p) as png:
                if png.mode != "L" or png.format != "PNG" or png.size != expected.source_size:
                    raise GeometryCorrectionError("Saved mask geometry is invalid")
                pixels = png.tobytes()
        except (OSError, UnidentifiedImageError, ValueError) as exc:
            raise GeometryCorrectionError("Cannot decode saved mask evidence") from exc
        if any(pixel not in (0, 255) for pixel in pixels):
            raise GeometryCorrectionError("Mask pixels must be binary")
        compatible = (
            p.name.startswith(prefix)
            and digest == expected.mask_sha256
            and raw == expected.mask_png
        )
        if p.name.startswith(prefix) and not compatible:
            raise GeometryCorrectionError("Current proposal mask evidence was modified")
        versions.append(
            ExistingMaskVersion(
                path=p,
                sha256=digest,
                source_size=expected.source_size,
                white_pixel_count=pixels.count(255),
                proposal_prefix=match.group(1),
                matches_current_proposal=compatible,
            )
        )
    return tuple(sorted(versions, key=lambda item: item.path.name))
