"""Issue #58: honest Stage B multi-field review and scoped, non-executable C1."""

import hashlib
import io
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
)

from vscs.application.caps.general_visual_correction_triage import (
    candidate_visual_triage,
    semantic_field_suggestions,
)
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
)
from vscs.application.caps.persistent_human_review import (
    load_human_review_session,
    save_human_review_session,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult

_DIAL = "its outermost surface below the surrounding shelf plane"
_ROI = NormalizedRegion(0.25, 0.35, 0.25, 0.30)
_QUOTES = {"geometry": _DIAL, "components": _DIAL}
_SHARED = "The single rotary dial must stay recessed below the shelf plane."


def _scenario(root: Path):
    asset = "CAP-PRP-002"
    image_dir = root / "Canonical Assets" / asset / "Images" / "Visual Candidates"
    image_dir.mkdir(parents=True)
    source = image_dir / "console-candidate-1.png"
    Image.new("RGB", (80, 60), (40, 50, 60)).save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (root / "Canonical Assets" / asset / ".metadata").mkdir()
    snapshot = SimpleNamespace(
        project_root=root,
        image_path=source,
        asset_id=asset,
        reference_id=1,
        image_sha256=digest,
        reference_role="supplementary",
        reference_status="candidate",
        specification_fingerprint="spec-v58",
        review_fingerprint="review-v58",
        accepted_fields=(
            ("geometry", f"Recessed dial with {_DIAL}."),
            ("components", f"Three buttons and rotary dial with {_DIAL}."),
            ("materials", "The housing has a matte graphite finish."),
        ),
    )
    report = CandidateQualityResult(
        snapshot=snapshot,
        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
        semantic=SimpleNamespace(
            decision=SimpleNamespace(value="regenerate"),
            violations=(
                "The rotary dial outermost surface protrudes above the shelf plane.",
                "The graphite housing appears otherwise correct.",
            ),
        ),
        recommendations=(),
    )
    triage = candidate_visual_triage(report)
    first = propose_spatial_evidence(
        triage,
        field="geometry",
        status=VisualEvidenceStatus.FAILED,
        observation="The rotary dial protrudes above the surrounding shelf plane.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=_ROI,
        expected_source_sha256=digest,
    )
    second = propose_spatial_evidence(
        triage,
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The control dial outermost surface violates the recessed layout.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=_ROI,
        previous=first,
        expected_source_sha256=digest,
    )
    reviewed = propose_spatial_evidence(
        triage,
        field="materials",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="The matte graphite finish is visually confirmed on the housing.",
        previous=second,
        expected_source_sha256=digest,
    )
    return snapshot, report, triage, reviewed


def _prepare(snapshot, review, **kwargs):
    return prepare_governed_correction_proposal(
        review,
        target_field="geometry",
        expected_source_sha256=snapshot.image_sha256,
        reviewer_confirmed_roi=True,
        **kwargs,
    )


def _correlated(snapshot, review):
    return _prepare(
        snapshot,
        review,
        correlated_field_quotes=_QUOTES,
        shared_atomic_constraint=_SHARED,
    )


def test_honest_correlated_double_failure_preserves_independent_third_review(tmp_path):
    snapshot, _report, _triage, review = _scenario(tmp_path)
    with pytest.raises(GeometryCorrectionError, match="Multiple FAILED"):
        _prepare(snapshot, review)
    proposal = _correlated(snapshot, review)
    proposal.verify_seal()
    assert proposal.schema_version == 2
    assert proposal.scoped_failed_fields == ("geometry", "components")
    assert proposal.separate_failed_fields == ()
    assert [status for _, status, _ in proposal.field_reviews] == [
        "FAILED",
        "FAILED",
        "VERIFIED_BY_OPERATOR",
    ]
    assert "Source CAP quote [components]" in proposal.describe()
    assert not proposal.can_generate
    assert not proposal.gpu_execution_authorized
    assert not proposal.governed_attempt_allowed
    assert not proposal.canon_approval_allowed


def test_unrelated_second_failure_requires_its_own_explicit_scope(tmp_path):
    snapshot, _report, _triage, review = _scenario(tmp_path)
    fields = list(review.reviewed_fields)
    fields[1] = replace(
        fields[1],
        defect=GeometryDefect.MISSING_COMPONENT,
        correction_stages=("reconstruct_component", "verify_design"),
        proposed_region=NormalizedRegion(0.65, 0.55, 0.2, 0.3),
    )
    unrelated = replace(review, reviewed_fields=tuple(fields))
    with pytest.raises(GeometryCorrectionError, match="share defect and exact ROI"):
        _correlated(snapshot, unrelated)
    with pytest.raises(GeometryCorrectionError, match="Multiple FAILED"):
        _prepare(snapshot, unrelated)
    separate = _prepare(snapshot, unrelated, confirm_separate_failures=True)
    assert separate.scoped_failed_fields == ("geometry",)
    assert separate.separate_failed_fields == ("components",)
    assert "separate corrections" in separate.describe()
    assert separate.field_reviews[1][1] == "FAILED"


def test_unknown_field_and_absent_roi_fail_closed(tmp_path):
    snapshot, _report, _triage, review = _scenario(tmp_path)
    unknown = replace(
        review,
        reviewed_fields=(
            *review.reviewed_fields[:-1],
            replace(
                review.reviewed_fields[-1], status=VisualEvidenceStatus.UNKNOWN, observation=""
            ),
        ),
    )
    with pytest.raises(GeometryCorrectionError, match="All accepted"):
        _correlated(snapshot, unknown)
    missing_roi = replace(
        review,
        reviewed_fields=(
            review.reviewed_fields[0],
            replace(review.reviewed_fields[1], proposed_region=None),
            review.reviewed_fields[2],
        ),
    )
    with pytest.raises(GeometryCorrectionError, match="share defect and exact ROI"):
        _correlated(snapshot, missing_roi)


def test_unverified_or_fabricated_correlation_is_rejected(tmp_path):
    snapshot, _report, _triage, review = _scenario(tmp_path)
    with pytest.raises(GeometryCorrectionError, match="ROI review"):
        prepare_governed_correction_proposal(
            review,
            target_field="geometry",
            expected_source_sha256=snapshot.image_sha256,
            reviewer_confirmed_roi=False,
            correlated_field_quotes=_QUOTES,
            shared_atomic_constraint=_SHARED,
        )
    with pytest.raises(GeometryCorrectionError, match="source identity"):
        prepare_governed_correction_proposal(
            review,
            target_field="geometry",
            expected_source_sha256="b" * 64,
            reviewer_confirmed_roi=True,
            correlated_field_quotes=_QUOTES,
            shared_atomic_constraint=_SHARED,
        )
    with pytest.raises(GeometryCorrectionError, match="exact accepted CAP source"):
        _prepare(
            snapshot,
            review,
            correlated_field_quotes={"geometry": "invented feature present", "components": _DIAL},
            shared_atomic_constraint=_SHARED,
        )
    with pytest.raises(GeometryCorrectionError, match="shared atomic"):
        _prepare(snapshot, review, correlated_field_quotes=_QUOTES)
    proposal = _correlated(snapshot, review)
    with pytest.raises(GeometryCorrectionError, match="scope is invalid"):
        replace(
            proposal, field_reviews=(("geometry", "VERIFIED_BY_OPERATOR", "fabricated"),)
        ).verify_seal()
    with pytest.raises(GeometryCorrectionError, match="authority"):
        replace(proposal, gpu_execution_authorized=True).verify_seal()


def test_correlated_scope_persists_and_reopens_without_authority(tmp_path):
    snapshot, _report, triage, review = _scenario(tmp_path)
    proposal = _correlated(snapshot, review)
    before = snapshot.image_path.read_bytes()
    path = save_human_review_session(snapshot, review, proposal=proposal)
    saved = load_human_review_session(snapshot, triage, path=path)
    assert saved.review == review
    assert saved.proposal_sha256 == proposal.proposal_sha256
    assert saved.c1_scope is not None
    assert saved.c1_scope.field_source_quotes == tuple(_QUOTES.items())
    assert (
        _prepare(
            snapshot,
            saved.review,
            correlated_field_quotes=dict(saved.c1_scope.field_source_quotes),
            shared_atomic_constraint=saved.c1_scope.shared_atomic_constraint,
        ).proposal_sha256
        == saved.proposal_sha256
    )
    assert snapshot.image_path.read_bytes() == before
    assert not saved.review.gpu_execution_authorized
    assert not saved.review.governed_attempt_allowed
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["payload"]["c1_scope"]["shared_atomic_constraint"] == _SHARED


def test_stale_source_or_correlated_session_tamper_is_rejected(tmp_path):
    snapshot, _report, triage, review = _scenario(tmp_path)
    path = save_human_review_session(snapshot, review, proposal=_correlated(snapshot, review))
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["c1_scope"]["field_source_quotes"][0][1] = "invented text"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(GeometryCorrectionError, match="seal"):
        load_human_review_session(snapshot, triage, path=path)
    snapshot.image_path.write_bytes(b"stale")
    with pytest.raises(GeometryCorrectionError, match="source changed"):
        load_human_review_session(snapshot, triage, path=path)


def test_correlated_mask_exact_polarity_and_protected_history(tmp_path):
    snapshot, _report, _triage, review = _scenario(tmp_path)
    protected = tmp_path / "protected-candidate-4.png"
    protected.write_bytes(b"historical immutable candidate placeholder")
    protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
    original = snapshot.image_path.read_bytes()
    proposal = _correlated(snapshot, review)
    mask = prepare_reviewed_mask(
        proposal, source_path=snapshot.image_path, reviewer_confirmed_mask=True
    )
    inspect_reviewed_mask(mask, proposal=proposal, source_path=snapshot.image_path)
    with Image.open(io.BytesIO(mask.mask_png)) as image:
        assert image.mode == "L"
        assert set(image.tobytes()) == {0, 255}
        left, top, right, bottom = mask.pixel_bounds
        assert image.getpixel((left, top)) == 255
        assert image.getpixel((right - 1, bottom - 1)) == 255
        assert image.getpixel((0, 0)) == 0
        assert image.getpixel((image.width - 1, image.height - 1)) == 0
    assert snapshot.image_path.read_bytes() == original
    assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_hash
    assert not mask.protected_pixels_verified  # Until actual generated output is checked.
    assert not mask.gpu_execution_authorized


def test_saved_semantic_suggestions_are_not_auto_confirmations(tmp_path):
    _snapshot, report, triage, review = _scenario(tmp_path)
    suggested = semantic_field_suggestions(report)
    assert "dial" in suggested["geometry"][0]
    assert "dial" in suggested["components"][0]
    assert "materials" in suggested
    assert triage.unresolved_mandatory_checks == 3
    assert review.reviewed_fields[0].status is VisualEvidenceStatus.FAILED
    assert not review.gpu_execution_authorized


def test_qt_offline_correlated_review_save_and_fresh_resume(tmp_path, qtbot, monkeypatch):
    from vscs.presentation.dialogs.source_image_roi_dialog import SourceImageRoiDialog
    from vscs.presentation.widgets.cap_visual_candidate_quality import (
        CandidateQualityReportDialog,
        _GuardedHumanReviewDialog,
    )

    snapshot, report, _triage, _review = _scenario(tmp_path)
    parent = QDialog()
    qtbot.addWidget(parent)
    errors: list[str] = []
    roi_reuse_confirmations: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: errors.append(message),
    )

    def confirm_roi(_parent, _title, message, *_args):
        roi_reuse_confirmations.append(message)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm_roi)

    def choose_roi(selector: SourceImageRoiDialog):
        selector.selected_region = _ROI
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SourceImageRoiDialog, "exec", choose_roi)

    def exercise_dialog(dialog: _GuardedHumanReviewDialog):
        def widget(cls, name):
            control = dialog.findChild(cls, name)
            assert control is not None, name
            return control

        fields = widget(QComboBox, "generalTriageReviewedField")
        state = widget(QComboBox, "spatialEvidenceStatus")
        defect = widget(QComboBox, "generalTriageDefectType")
        reason = widget(QPlainTextEdit, "generalTriageObservedFailure")
        suggestion = widget(QPlainTextEdit, "stageBSourceSemanticSuggestions")
        assert "rotary dial" in suggestion.toPlainText()
        assert state.currentData() == "UNKNOWN"

        for field, status, observation in (
            ("geometry", "FAILED", "The rotary dial protrudes above the shelf plane."),
            ("components", "FAILED", "The rotary dial violates the recessed layout."),
            ("materials", "VERIFIED_BY_OPERATOR", "The matte graphite finish looks correct."),
        ):
            fields.setCurrentIndex(fields.findData(field))
            state.setCurrentIndex(state.findData(status))
            reason.setPlainText(observation)
            if status == "FAILED":
                defect.setCurrentIndex(
                    defect.findData(GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED.value)
                )
                if field == "components":
                    widget(QPushButton, "stageBReuseReviewedFailedROI").click()
                else:
                    widget(QPushButton, "stageC2SelectSourceROI").click()
            widget(QPushButton, "spatialEvidenceInspect").click()

        progress = widget(QLabel, "spatialEvidenceReviewProgress")
        assert "2 FAILED, 1 VERIFIED, 0 UNKNOWN" in progress.text()
        assert len(roi_reuse_confirmations) == 1
        fields.setCurrentIndex(fields.findData("geometry"))
        widget(QLineEdit, "stageC1SharedAtomicConstraint").setText(_SHARED)
        widget(QPlainTextEdit, "stageC1CorrelatedSourceQuotes").setPlainText(
            "\n".join(f"{field}|{quote}" for field, quote in _QUOTES.items())
        )
        widget(QCheckBox, "stageCReviewedROIConfirmation").setChecked(True)
        widget(QPushButton, "stageCGovernedCorrectionInspect").click()
        details = widget(QPlainTextEdit, "generalTriageAssessment")
        assert "Scoped FAILED fields: geometry, components" in details.toPlainText()
        assert "VERIFIED_BY_OPERATOR" in details.toPlainText()
        assert not errors

        widget(QPushButton, "c21SaveHumanReview").click()
        status_label = widget(QLabel, "c21InlineReviewStatus")
        assert "SAVED immutable C2.1" in status_label.text()
        widget(QPushButton, "c21ResumeHumanReview").click()
        assert "RESTORED" in status_label.text()
        assert not widget(QCheckBox, "stageCReviewedROIConfirmation").isChecked()
        assert widget(QLineEdit, "stageC1SharedAtomicConstraint").text() == _SHARED
        assert "2 FAILED, 1 VERIFIED" in progress.text()
        widget(QCheckBox, "stageCReviewedROIConfirmation").setChecked(True)
        widget(QPushButton, "stageCGovernedCorrectionInspect").click()
        assert "Scoped FAILED fields: geometry, components" in details.toPlainText()
        assert not errors
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(_GuardedHumanReviewDialog, "exec", exercise_dialog)
    CandidateQualityReportDialog._open_general_correction_triage(parent, report)
    sessions = tuple(
        (
            tmp_path / "Canonical Assets" / snapshot.asset_id / ".metadata" / "human_visual_reviews"
        ).glob("*.json")
    )
    assert len(sessions) == 1
