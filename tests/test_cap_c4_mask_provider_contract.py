"""C4A: non-executable masked-provider contract and read-only pixel audit."""

import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from vscs.application.caps.c4_mask_provider_contract import (
    acknowledge_c4_review,
    audit_external_masked_result,
    prepare_c4_provider_contract,
)
from vscs.application.caps.general_visual_correction_triage import candidate_visual_triage
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
from vscs.application.caps.governed_visual_correction_handoff import (
    prepare_governed_correction_proposal,
)
from vscs.application.caps.human_reviewed_mask_evidence import (
    prepare_reviewed_mask,
    save_reviewed_mask_once,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


def _fixture(tmp_path: Path):
    project = tmp_path / "acceptance_project"
    image_folder = (
        project / "Canonical Assets" / "STORY-C4A-TEST" / "Images" / "Visual Candidates"
    )
    image_folder.mkdir(parents=True)
    source_path = image_folder / "candidate.png"
    Image.new("RGB", (320, 256), (20, 40, 60)).save(source_path)
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    snapshot = SimpleNamespace(
        project_root=project.resolve(),
        image_path=source_path.resolve(),
        asset_id="STORY-C4A-TEST",
        reference_id=4,
        image_sha256=digest,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "Three buttons and recessed dial"),
            ("geometry", "Standing console beside independent workstation"),
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
        observation="The rotary dial protrudes instead of being recessed.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=NormalizedRegion(0.2, 0.2, 0.2, 0.3),
    )
    review = propose_spatial_evidence(
        triage,
        previous=review,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="The adjacent workstation is visually separate.",
    )
    proposal = prepare_governed_correction_proposal(
        review,
        target_field="components",
        expected_source_sha256=digest,
        reviewer_confirmed_roi=True,
    )
    mask_dir = project / "Canonical Assets" / snapshot.asset_id / ".metadata" / "spatial_masks"
    mask_dir.mkdir(parents=True)
    evidence = prepare_reviewed_mask(
        proposal, source_path=source_path, reviewer_confirmed_mask=True
    )
    mask = save_reviewed_mask_once(
        evidence,
        proposal=proposal,
        source_path=source_path,
        destination_directory=mask_dir,
    )
    return snapshot, proposal, mask, evidence


def test_preparation_sealed_and_no_provider_or_attempt_authority(tmp_path, monkeypatch):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    original_source = snapshot.image_path.read_bytes()
    original_mask = mask.read_bytes()
    monkeypatch.setattr(
        "vscs.application.caps.c4_mask_provider_contract._get_json",
        lambda *_args: pytest.fail("C4A must not call ComfyUI"),
        raising=False,
    )
    receipt = prepare_c4_provider_contract(snapshot, proposal, selected_mask_path=mask)
    receipt.verify_seal()
    assert receipt.mask_matches_current_proposal
    assert receipt.mask_node_wiring_validated_offline
    assert receipt.derived_graph_sha256
    assert receipt.managed_workflow_sha256
    assert not receipt.execution_authorized
    assert not receipt.mask_provider_compatibility_verified
    assert not receipt.pixel_preservation_verified
    assert not receipt.attempt_reservation_allowed
    assert not receipt.candidate_registration_allowed
    assert receipt.blockers
    assert snapshot.image_path.read_bytes() == original_source
    assert mask.read_bytes() == original_mask
    assert sorted(path.name for path in mask.parent.iterdir()) == [mask.name]


def test_historical_and_missing_mask_fail_closed(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    no_mask = prepare_c4_provider_contract(
        snapshot, proposal, selected_mask_path=None
    )
    assert not no_mask.mask_matches_current_proposal
    assert any("explicitly" in item for item in no_mask.blockers)
    digest = hashlib.sha256(mask.read_bytes()).hexdigest()
    historical = mask.parent / f"c2-4-ffffffffffffffff-{digest[:16]}.png"
    historical.write_bytes(mask.read_bytes())
    old = prepare_c4_provider_contract(
        snapshot, proposal, selected_mask_path=historical
    )
    assert not old.mask_matches_current_proposal
    assert any("HISTORICAL" in item for item in old.blockers)
    assert not old.execution_authorized


def test_source_and_cap_mismatch_rejected(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    changed = SimpleNamespace(
        **{**vars(snapshot), "accepted_fields": (("components", "Different"),)}
    )
    with pytest.raises(GeometryCorrectionError, match="source/CAP"):
        prepare_c4_provider_contract(changed, proposal, selected_mask_path=mask)
    snapshot.image_path.write_bytes(b"corrupt source")
    with pytest.raises(GeometryCorrectionError, match="source changed"):
        prepare_c4_provider_contract(snapshot, proposal, selected_mask_path=mask)


def test_review_acknowledgement_requires_exact_text_and_never_executes(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    prepared = prepare_c4_provider_contract(snapshot, proposal, selected_mask_path=mask)
    for wrong in ("", "yes", "GENERATE", "REVIEW ONLY ", "review only"):
        with pytest.raises(GeometryCorrectionError, match="REVIEW ONLY"):
            acknowledge_c4_review(prepared, operator_text=wrong)
    acknowledgment = acknowledge_c4_review(prepared, operator_text="REVIEW ONLY")
    assert acknowledgment.preparation_sha256 == prepared.evidence_sha256
    assert not acknowledgment.execution_authorized
    assert not acknowledgment.attempt_reservation_allowed
    with pytest.raises(GeometryCorrectionError, match="seal"):
        acknowledge_c4_review(
            replace(prepared, source_sha256="a" * 64), operator_text="REVIEW ONLY"
        )


def test_external_pixel_audit_detects_protected_pixel_change(tmp_path):
    snapshot, proposal, mask, evidence = _fixture(tmp_path)
    result = tmp_path / "external_result.png"
    with Image.open(snapshot.image_path) as image:
        edited = image.copy()
    # Modify one pixel within operator-selected rectangle.
    x0, y0, _, _ = evidence.pixel_bounds
    edited.putpixel((x0, y0), (255, 255, 255))
    edited.save(result)
    first = audit_external_masked_result(
        snapshot, proposal, selected_mask_path=mask, external_result_path=result
    )
    assert first.protected_pixels_identical
    assert first.changed_protected_pixels == 0
    assert first.editable_pixels == evidence.selected_pixels
    assert not first.candidate_registration_allowed
    # A single changed pixel outside the mask must fail preservation.
    edited.putpixel((0, 0), (255, 255, 255))
    edited.save(result)
    second = audit_external_masked_result(
        snapshot, proposal, selected_mask_path=mask, external_result_path=result
    )
    assert not second.protected_pixels_identical
    assert second.changed_protected_pixels == 1


def test_audit_rejects_project_output_mismatch_and_symlinks(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    output = snapshot.image_path.parent / "generated_inside_project.png"
    Image.new("RGB", (320, 256)).save(output)
    with pytest.raises(GeometryCorrectionError, match="external"):
        audit_external_masked_result(
            snapshot, proposal, selected_mask_path=mask, external_result_path=output
        )
    other = tmp_path / "different_size.png"
    Image.new("RGB", (32, 32)).save(other)
    with pytest.raises(GeometryCorrectionError, match="equal-sized"):
        audit_external_masked_result(
            snapshot, proposal, selected_mask_path=mask, external_result_path=other
        )


def test_invalid_graph_does_not_enable_provider(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    malformed = tmp_path / "bad_api.json"
    malformed.write_text("{}", encoding="utf-8")
    prepared = prepare_c4_provider_contract(
        snapshot, proposal, selected_mask_path=mask, workflow_path=malformed
    )
    assert not prepared.mask_node_wiring_validated_offline
    assert any("topology unavailable" in item for item in prepared.blockers)
    assert not prepared.execution_authorized
