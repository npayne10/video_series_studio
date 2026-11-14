"""F5.4.2 C2: deterministic, source-bound, operator-reviewed mask evidence.

White means *proposed editable pixels*; black means protected. An inspected mask
is never provider consent, an authorized correction, or proof of pixel preservation.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError

from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
)

_MAX_PIXELS = 40_000_000


@dataclass(frozen=True, slots=True)
class ReviewedMaskEvidence:
    proposal_sha256: str
    source_sha256: str
    source_size: tuple[int, int]
    pixel_bounds: tuple[int, int, int, int]
    mask_sha256: str
    selected_pixels: int
    reviewer_confirmed: bool
    mask_png: bytes = field(repr=False)
    mask_verified: bool = False
    protected_pixels_verified: bool = False
    provider_mask_capability_verified: bool = False
    gpu_execution_authorized: bool = False
    governed_attempt_allowed: bool = False
    candidate_registration_allowed: bool = False
    cap_approval_allowed: bool = False
    canon_approval_allowed: bool = False

    def describe(self) -> str:
        return "\n".join(
            (
                "F5.4.2 C2 - REVIEWED MASK EVIDENCE (NO GENERATION)",
                f"Correction proposal: {self.proposal_sha256}",
                f"Source SHA-256: {self.source_sha256}",
                f"Source dimensions: {self.source_size[0]} x {self.source_size[1]}",
                f"Pixel bounds [left,top,right,bottom]: {self.pixel_bounds}",
                f"Editable pixel count: {self.selected_pixels}",
                f"Mask PNG SHA-256: {self.mask_sha256}",
                "White = proposed editable region; black = protected region.",
                "Operator preview acknowledged; this does NOT validate a provider mask input.",
                "No pixel-preservation proof exists until after an actual correction.",
                "No GPU generation, attempt reservation, Candidate registration or approval.",
            )
        )


def _source_image(path: Path, proposal: GovernedCorrectionProposal) -> tuple[int, int]:
    proposal.verify_seal()
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".png":
        raise GeometryCorrectionError("Source must be an existing non-symlink PNG Candidate")
    resolved = path.resolve(strict=True)
    # Only the canonical asset Candidate directory is eligible.
    if (
        resolved.parent.name != "Visual Candidates"
        or resolved.parent.parent.name != "Images"
        or resolved.parent.parent.parent.name != proposal.asset_id
        or resolved.parent.parent.parent.parent.name != "Canonical Assets"
        or path != resolved
    ):
        raise GeometryCorrectionError("Source path is not a canonical Candidate image")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise GeometryCorrectionError("Unable to read Candidate image") from exc
    if hashlib.sha256(raw).hexdigest() != proposal.source_sha256:
        raise GeometryCorrectionError("Source Candidate SHA-256 mismatch")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG":
                raise GeometryCorrectionError("Source image must be PNG")
            size = image.size
            if not 0 < size[0] * size[1] <= _MAX_PIXELS:
                raise GeometryCorrectionError("Source image dimensions exceed safe limit")
            image.verify()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise GeometryCorrectionError("Source image is not a valid PNG") from exc
    return size


def _bounds(
    proposal: GovernedCorrectionProposal, size: tuple[int, int]
) -> tuple[int, int, int, int]:
    # Decimal conversion avoids binary float error at exact pixel boundaries.
    roi = proposal.reviewed_roi
    width, height = size
    left = int((Decimal(str(roi.x)) * width).to_integral_value(rounding=ROUND_FLOOR))
    top = int((Decimal(str(roi.y)) * height).to_integral_value(rounding=ROUND_FLOOR))
    right = int(
        ((Decimal(str(roi.x)) + Decimal(str(roi.width))) * width).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    bottom = int(
        ((Decimal(str(roi.y)) + Decimal(str(roi.height))) * height).to_integral_value(
            rounding=ROUND_CEILING
        )
    )
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise GeometryCorrectionError("Review ROI collapses or exceeds source-image pixels")
    return left, top, right, bottom


def preview_mask_bounds(
    proposal: GovernedCorrectionProposal, *, source_path: Path
) -> tuple[tuple[int, int], tuple[int, int, int, int]]:
    """Validate source and raster bounds without making an approval claim."""
    size = _source_image(source_path, proposal)
    return size, _bounds(proposal, size)


def prepare_reviewed_mask(
    proposal: GovernedCorrectionProposal,
    *,
    source_path: Path,
    reviewer_confirmed_mask: bool,
) -> ReviewedMaskEvidence:
    """Build exact 8-bit grayscale PNG evidence in memory; no file writes."""
    if type(reviewer_confirmed_mask) is not bool or not reviewer_confirmed_mask:
        raise GeometryCorrectionError("Mask preview requires explicit operator confirmation")
    size = _source_image(source_path, proposal)
    bounds = _bounds(proposal, size)
    mask = Image.new("L", size, color=0)
    ImageDraw.Draw(mask).rectangle((bounds[0], bounds[1], bounds[2] - 1, bounds[3] - 1), fill=255)
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    png = buffer.getvalue()
    return ReviewedMaskEvidence(
        proposal_sha256=proposal.proposal_sha256,
        source_sha256=proposal.source_sha256,
        source_size=size,
        pixel_bounds=bounds,
        mask_sha256=hashlib.sha256(png).hexdigest(),
        selected_pixels=(bounds[2] - bounds[0]) * (bounds[3] - bounds[1]),
        reviewer_confirmed=True,
        mask_png=png,
    )


def inspect_reviewed_mask(
    evidence: ReviewedMaskEvidence,
    *,
    proposal: GovernedCorrectionProposal,
    source_path: Path,
) -> None:
    """Verify source, exact mask bytes, raster extent, and no-authority boundary."""
    size = _source_image(source_path, proposal)
    if (
        not evidence.reviewer_confirmed
        or evidence.proposal_sha256 != proposal.proposal_sha256
        or evidence.source_sha256 != proposal.source_sha256
        or evidence.source_size != size
        or evidence.pixel_bounds != _bounds(proposal, size)
        or hashlib.sha256(evidence.mask_png).hexdigest() != evidence.mask_sha256
        or evidence.mask_verified
        or evidence.protected_pixels_verified
        or evidence.provider_mask_capability_verified
        or evidence.gpu_execution_authorized
        or evidence.governed_attempt_allowed
        or evidence.candidate_registration_allowed
        or evidence.cap_approval_allowed
        or evidence.canon_approval_allowed
    ):
        raise GeometryCorrectionError("Mask evidence or no-authority boundary changed")
    try:
        with Image.open(io.BytesIO(evidence.mask_png)) as mask:
            if mask.format != "PNG" or mask.mode != "L" or mask.size != size:
                raise GeometryCorrectionError("Mask format or dimensions changed")
            pixels = mask.tobytes()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise GeometryCorrectionError("Mask PNG is invalid") from exc
    left, top, right, bottom = evidence.pixel_bounds
    width, height = size
    if evidence.selected_pixels != (right - left) * (bottom - top):
        raise GeometryCorrectionError("Mask area differs from reviewed ROI")
    protected = bytes(width)
    active = bytes([255]) * (right - left)
    review_row = bytes(left) + active + bytes(width - right)
    for y in range(height):
        expected = review_row if top <= y < bottom else protected
        if pixels[y * width : (y + 1) * width] != expected:
            raise GeometryCorrectionError("Mask pixels differ from reviewed ROI")


def save_reviewed_mask_once(
    evidence: ReviewedMaskEvidence,
    *,
    proposal: GovernedCorrectionProposal,
    source_path: Path,
    destination_directory: Path,
) -> Path:
    """Explicit exclusive artifact write, never an image/CAP/attempt write.

    Destination must already be the canonical asset .metadata/spatial_masks directory.
    C2 does not create directories, overwrite files, or enroll masks with ComfyUI.
    """
    inspect_reviewed_mask(evidence, proposal=proposal, source_path=source_path)
    asset_dir = source_path.parent.parent.parent
    expected = asset_dir / ".metadata" / "spatial_masks"
    if (
        destination_directory != expected
        or destination_directory.is_symlink()
        or not destination_directory.is_dir()
        or destination_directory.resolve(strict=True) != destination_directory
    ):
        raise GeometryCorrectionError(
            "Mask destination must be existing canonical evidence directory"
        )
    name = f"c2-{proposal.source_reference_id}-{proposal.proposal_sha256[:16]}-{evidence.mask_sha256[:16]}.png"
    path = destination_directory / name
    if path.exists() or path.is_symlink():
        raise GeometryCorrectionError("Mask evidence already exists; never overwrite")
    try:
        with path.open("xb") as stream:
            stream.write(evidence.mask_png)
    except OSError as exc:
        raise GeometryCorrectionError("Could not exclusively save reviewed mask") from exc
    return path
