"""C2.1 immutable human-session persistence and explicit historical mask listing."""

import hashlib
import json
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
    prepare_reviewed_mask,
    save_reviewed_mask_once,
)
from vscs.application.caps.persistent_human_review import (
    list_existing_mask_versions,
    list_human_review_sessions,
    load_human_review_session,
    save_human_review_session,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


def _scenario(tmp_path: Path):
    root = tmp_path.resolve()
    asset = "STORY-C21-TEST"
    images = root / "Canonical Assets" / asset / "Images" / "Visual Candidates"
    images.mkdir(parents=True)
    image = images / "candidate.png"
    Image.new("RGB", (40, 30), (40, 70, 90)).save(image)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    snapshot = SimpleNamespace(
        project_root=root,
        image_path=image,
        asset_id=asset,
        reference_id=4,
        image_sha256=digest,
        reference_role="supplementary",
        reference_status="candidate",
        specification_fingerprint="spec-v1",
        review_fingerprint="review-v1",
        accepted_fields=(
            ("components", "Three controls and recessed rotary dial"),
            ("geometry", "Separate workstation and standing console"),
        ),
    )
    report = CandidateQualityResult(
        snapshot=snapshot,
        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
        semantic=None,
        recommendations=(),
    )
    triage = candidate_visual_triage(report)
    one = propose_spatial_evidence(
        triage,
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The right rotary dial stands above the control surface.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=NormalizedRegion(0.1, 0.2, 0.3, 0.4),
    )
    reviewed = propose_spatial_evidence(
        triage,
        previous=one,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="Workstation and console appear physically separate.",
    )
    proposal = prepare_governed_correction_proposal(
        reviewed,
        target_field="components",
        expected_source_sha256=digest,
        reviewer_confirmed_roi=True,
    )
    metadata = root / "Canonical Assets" / asset / ".metadata"
    metadata.mkdir()
    return snapshot, triage, reviewed, proposal


def test_immutable_save_reload_and_fresh_operator_confirmations(tmp_path):
    snapshot, triage, review, proposal = _scenario(tmp_path)
    old_source = snapshot.image_path.read_bytes()
    path = save_human_review_session(snapshot, review, proposal=proposal)
    assert path.exists()
    saved = load_human_review_session(snapshot, triage, path=path)
    assert saved.review == review
    assert saved.proposal_sha256 == proposal.proposal_sha256
    assert saved.review.outstanding_fields == 0
    assert not saved.review.gpu_execution_authorized
    assert not saved.review.governed_attempt_allowed
    assert not saved.review.cap_registration_allowed
    assert snapshot.image_path.read_bytes() == old_source
    second = save_human_review_session(snapshot, review, proposal=proposal)
    assert second != path
    assert path.read_bytes() != b""
    assert set(list_human_review_sessions(snapshot)) == {path, second}


def test_partial_review_resume_does_not_invent_passes(tmp_path):
    snapshot, triage, review, _proposal = _scenario(tmp_path)
    partial = propose_spatial_evidence(
        triage,
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The right rotary dial stands above the control surface.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=NormalizedRegion(0.1, 0.2, 0.3, 0.4),
    )
    assert review.outstanding_fields == 0
    saved = save_human_review_session(snapshot, partial)
    restored = load_human_review_session(snapshot, triage, path=saved)
    assert restored.review.outstanding_fields == 1
    assert restored.proposal_sha256 is None


def test_stale_source_or_changed_cap_fails_closed(tmp_path):
    snapshot, triage, review, proposal = _scenario(tmp_path)
    path = save_human_review_session(snapshot, review, proposal=proposal)
    changed = SimpleNamespace(**{**vars(snapshot), "review_fingerprint": "modified"})
    with pytest.raises(GeometryCorrectionError, match="stale"):
        load_human_review_session(changed, triage, path=path)
    snapshot.image_path.write_bytes(b"changed")
    with pytest.raises(GeometryCorrectionError, match="source changed"):
        load_human_review_session(snapshot, triage, path=path)
    with pytest.raises(GeometryCorrectionError, match="source changed"):
        save_human_review_session(snapshot, review)


def test_tampered_evidence_or_permissions_blocked(tmp_path):
    snapshot, triage, review, proposal = _scenario(tmp_path)
    path = save_human_review_session(snapshot, review, proposal=proposal)
    content = json.loads(path.read_text(encoding="utf-8"))
    content["payload"]["fields"][0]["observation"] = "forged evidence"
    path.write_text(json.dumps(content), encoding="utf-8")
    with pytest.raises(GeometryCorrectionError, match="seal"):
        load_human_review_session(snapshot, triage, path=path)
    with pytest.raises(GeometryCorrectionError, match="authoritative"):
        save_human_review_session(
            snapshot, replace(review, governed_attempt_allowed=True)
        )


def test_c1_digest_must_be_derived_from_same_review(tmp_path):
    snapshot, _triage, review, proposal = _scenario(tmp_path)
    fields = list(review.reviewed_fields)
    fields[0] = replace(fields[0], observation="The operator recorded a different defect.")
    with pytest.raises(GeometryCorrectionError):
        save_human_review_session(
            snapshot, replace(review, reviewed_fields=tuple(fields)), proposal=proposal
        )


def test_existing_mask_versions_are_explicit_and_no_auto_adoption(tmp_path):
    snapshot, _triage, review, proposal = _scenario(tmp_path)
    evidence = prepare_reviewed_mask(
        proposal, source_path=snapshot.image_path, reviewer_confirmed_mask=True
    )
    destination = (
        snapshot.project_root
        / "Canonical Assets"
        / snapshot.asset_id
        / ".metadata"
        / "spatial_masks"
    )
    destination.mkdir()
    first = save_reviewed_mask_once(
        evidence,
        proposal=proposal,
        source_path=snapshot.image_path,
        destination_directory=destination,
    )
    other = prepare_governed_correction_proposal(
        propose_spatial_evidence(
            candidate_visual_triage(
                CandidateQualityResult(
                    snapshot=snapshot,
                    technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
                    semantic=None,
                    recommendations=(),
                )
            ),
            field="components",
            status=VisualEvidenceStatus.FAILED,
            observation="The dial mounting region must be recessed into the panel.",
            defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
            region=NormalizedRegion(0.2, 0.2, 0.2, 0.3),
            previous=propose_spatial_evidence(
                candidate_visual_triage(
                    CandidateQualityResult(
                        snapshot=snapshot,
                        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
                        semantic=None,
                        recommendations=(),
                    )
                ),
                previous=None,
                field="geometry",
                status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
                observation="Workstation and console appear physically separate.",
            ),
        ),
        target_field="components",
        expected_source_sha256=snapshot.image_sha256,
        reviewer_confirmed_roi=True,
    )
    second_evidence = prepare_reviewed_mask(
        other, source_path=snapshot.image_path, reviewer_confirmed_mask=True
    )
    second = save_reviewed_mask_once(
        second_evidence,
        proposal=other,
        source_path=snapshot.image_path,
        destination_directory=destination,
    )
    versions = list_existing_mask_versions(snapshot, proposal=proposal)
    assert {v.path for v in versions} == {first, second}
    assert len([v for v in versions if v.matches_current_proposal]) == 1
    assert len([v for v in versions if not v.matches_current_proposal]) == 1
    assert not review.gpu_execution_authorized


def test_saved_mask_file_tampering_detected(tmp_path):
    snapshot, _triage, _review, proposal = _scenario(tmp_path)
    evidence = prepare_reviewed_mask(
        proposal, source_path=snapshot.image_path, reviewer_confirmed_mask=True
    )
    destination = (
        snapshot.project_root
        / "Canonical Assets"
        / snapshot.asset_id
        / ".metadata"
        / "spatial_masks"
    )
    destination.mkdir()
    mask = save_reviewed_mask_once(
        evidence, proposal=proposal, source_path=snapshot.image_path,
        destination_directory=destination,
    )
    mask.write_bytes(b"invalid changed bytes")
    with pytest.raises(GeometryCorrectionError, match="digest"):
        list_existing_mask_versions(snapshot, proposal=proposal)


def test_unsaved_review_guard_blocks_window_close_and_escape(qtbot):
    from PySide6.QtWidgets import QWidget

    from vscs.presentation.widgets.cap_visual_candidate_quality import (
        _GuardedHumanReviewDialog,
    )

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = _GuardedHumanReviewDialog(parent)
    qtbot.addWidget(dialog)
    dialog.can_close = lambda: False
    dialog.show()
    dialog.reject()
    assert dialog.isVisible()
    assert not dialog.close()
    assert dialog.isVisible()
    dialog.can_close = lambda: True
    assert dialog.close()
    assert not dialog.isVisible()
