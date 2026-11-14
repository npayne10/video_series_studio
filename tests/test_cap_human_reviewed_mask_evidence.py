"""Stage C2 requires exact source-bound mask bytes with no execution authority."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from vscs.application.caps.general_visual_correction_triage import candidate_visual_triage
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.governed_visual_correction_handoff import (
    prepare_governed_correction_proposal,
)
from vscs.application.caps.human_reviewed_mask_evidence import (
    inspect_reviewed_mask,
    prepare_reviewed_mask,
    preview_mask_bounds,
    save_reviewed_mask_once,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


def _source(tmp_path: Path) -> Path:
    directory = tmp_path / "Canonical Assets" / "STORY-TEST" / "Images" / "Visual Candidates"
    directory.mkdir(parents=True)
    source = directory / "candidate.png"
    Image.new("RGB", (40, 30), (70, 80, 90)).save(source)
    return source


def _proposal(source: Path):
    import hashlib

    image_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    snapshot = SimpleNamespace(
        asset_id="STORY-TEST",
        reference_id=3,
        image_sha256=image_hash,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "Four approved physical controls"),
            ("materials", "Matte painted aluminum"),
        ),
    )
    report = CandidateQualityResult(
        snapshot=snapshot,
        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
        semantic=None,
        recommendations=(),
    )
    triage = candidate_visual_triage(report)
    review = propose_spatial_evidence(
        triage,
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The left rotary control is absent from the source.",
        defect=GeometryDefect.MISSING_COMPONENT,
        region=NormalizedRegion(0.1, 0.2, 0.3, 0.4),
    )
    review = propose_spatial_evidence(
        triage,
        previous=review,
        field="materials",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="Painted aluminum is visually confirmed on the housing.",
    )
    return prepare_governed_correction_proposal(
        review,
        target_field="components",
        expected_source_sha256=image_hash,
        reviewer_confirmed_roi=True,
    )


def test_deterministic_mask_exact_bounds_and_immutable_source(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    original = source.read_bytes()
    first = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    second = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    inspect_reviewed_mask(first, proposal=proposal, source_path=source)
    assert first.mask_png == second.mask_png
    assert first.mask_sha256 == second.mask_sha256
    assert first.source_size == (40, 30)
    assert first.pixel_bounds == (4, 6, 16, 18)
    assert first.selected_pixels == 144
    assert source.read_bytes() == original
    assert not first.mask_verified
    assert not first.protected_pixels_verified
    assert not first.gpu_execution_authorized
    assert not first.governed_attempt_allowed
    assert not first.candidate_registration_allowed


def test_preview_only_returns_pixel_bounds_without_artifacts(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    before = source.read_bytes()
    size, bounds = preview_mask_bounds(proposal, source_path=source)
    assert size == (40, 30)
    assert bounds == (4, 6, 16, 18)
    assert source.read_bytes() == before
    assert not (source.parent.parent.parent / ".metadata").exists()


def test_explicit_mask_confirmation_required(tmp_path):
    source = _source(tmp_path)
    with pytest.raises(GeometryCorrectionError, match="explicit operator"):
        prepare_reviewed_mask(_proposal(source), source_path=source, reviewer_confirmed_mask=False)


def test_source_changed_after_seal_refuses_mask(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    evidence = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    Image.new("RGB", (40, 30), (50, 30, 20)).save(source)
    with pytest.raises(GeometryCorrectionError, match="SHA-256 mismatch"):
        inspect_reviewed_mask(evidence, proposal=proposal, source_path=source)


def test_modified_mask_bytes_or_authority_rejected(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    evidence = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    with pytest.raises(GeometryCorrectionError, match="Mask evidence"):
        inspect_reviewed_mask(
            replace(evidence, mask_png=evidence.mask_png + b"extra"),
            proposal=proposal,
            source_path=source,
        )
    with pytest.raises(GeometryCorrectionError, match="Mask evidence"):
        inspect_reviewed_mask(
            replace(evidence, governed_attempt_allowed=True),
            proposal=proposal,
            source_path=source,
        )


def test_pixel_tampering_rejected_even_with_recomputed_digest(tmp_path):
    import hashlib
    import io

    source = _source(tmp_path)
    proposal = _proposal(source)
    evidence = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    with Image.open(io.BytesIO(evidence.mask_png)) as mask:
        altered = mask.copy()
    altered.putpixel((0, 0), 255)
    buffer = io.BytesIO()
    altered.save(buffer, format="PNG")
    payload = buffer.getvalue()
    with pytest.raises(GeometryCorrectionError, match="Mask pixels"):
        inspect_reviewed_mask(
            replace(
                evidence,
                mask_png=payload,
                mask_sha256=hashlib.sha256(payload).hexdigest(),
            ),
            proposal=proposal,
            source_path=source,
        )


def test_mask_evidence_exclusive_storage_and_no_candidate_mutation(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    evidence = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    metadata = source.parent.parent.parent / ".metadata"
    destination = metadata / "spatial_masks"
    destination.mkdir(parents=True)
    before = source.read_bytes()
    path = save_reviewed_mask_once(
        evidence,
        proposal=proposal,
        source_path=source,
        destination_directory=destination,
    )
    assert path.read_bytes() == evidence.mask_png
    assert source.read_bytes() == before
    with pytest.raises(GeometryCorrectionError, match="already exists"):
        save_reviewed_mask_once(
            evidence,
            proposal=proposal,
            source_path=source,
            destination_directory=destination,
        )


def test_unsafe_destination_blocked(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    evidence = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    with pytest.raises(GeometryCorrectionError, match="canonical evidence"):
        save_reviewed_mask_once(
            evidence,
            proposal=proposal,
            source_path=source,
            destination_directory=tmp_path,
        )


def test_invalid_candidate_directory_blocked(tmp_path):
    source = _source(tmp_path)
    proposal = _proposal(source)
    copied = tmp_path / "detached.png"
    copied.write_bytes(source.read_bytes())
    with pytest.raises(GeometryCorrectionError, match="canonical Candidate"):
        prepare_reviewed_mask(proposal, source_path=copied, reviewer_confirmed_mask=True)
