"""B.5.26 candidate-quality review: evidence, consent and no implicit approval."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QMessageBox

from vscs.application.caps.visual_candidate_quality import (
    CandidateQualityError,
    CandidateQualityReviewService,
)
from vscs.application.caps.visual_identity_preparation import VisualIdentityPreparation
from vscs.application.siee.models import SemanticMetric, SemanticModelResult
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
)
from vscs.presentation.widgets.cap_visual_candidate_quality import (
    CandidateQualityReportDialog,
    _review_selected,
)


def _scenario(tmp_path: Path):
    asset_id = "STORY-LOC-001"
    image_dir = tmp_path / "Canonical Assets" / asset_id / "Images" / "Visual Candidates"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "room.png"
    image = QImage(960, 600, QImage.Format.Format_RGB32)
    image.fill(QColor(125, 125, 125))
    assert image.save(str(image_path), "PNG")
    digest = hashlib.sha256(image_path.read_bytes()).hexdigest()

    preparation = VisualIdentityPreparation(
        asset_id=asset_id,
        title="Engineering control room",
        category=AssetCategory.LOCATION,
        specification_fingerprint="spec-v1",
        review_fingerprint="review-v1",
        accepted_fields=(("layout", "A rectangular room with a single door."),),
        deferred_fields=("lighting", "architecture"),
        continuity_context=("The console sits beside the workstation.",),
        dependency_asset_ids=(),
        blockers=(),
        master_candidate_prompt="PROPOSED room",
        negative_prompt="no extra doors",
        required_reference_views=(),
        missing_reference_views=(),
    )
    manifest = tmp_path / "Canonical Assets" / asset_id / ".metadata" / "visual" / "room.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {
                "asset_id": asset_id,
                "image_sha256": digest,
                "specification_fingerprint": "spec-v1",
                "review_fingerprint": "review-v1",
                "governance": "non-authoritative_candidate_not_MASTER",
                "prompt": "PROPOSED room",
            }
        ),
        encoding="utf-8",
    )
    reference = SimpleNamespace(
        id=7,
        cap_id=9,
        reference_type=CanonicalReferenceType.IMAGE,
        role=CanonicalReferenceRole.SUPPLEMENTARY,
        status=CanonicalReferenceStatus.CANDIDATE,
        locked=False,
        file_path=image_path.relative_to(tmp_path),
        description="PROPOSED room",
    )
    cap = SimpleNamespace(id=9, asset_id=asset_id, production_metadata={})
    asset = SimpleNamespace(
        asset_id=asset_id, name="Engineering control room", category=AssetCategory.LOCATION
    )
    refs = SimpleNamespace(
        get=Mock(return_value=reference),
        list_for_cap=Mock(return_value=(reference,)),
        approve=Mock(),
        archive=Mock(),
        set_primary=Mock(),
        caps=SimpleNamespace(
            get=Mock(return_value=cap),
            assets=SimpleNamespace(
                get=Mock(return_value=asset),
                projects=SimpleNamespace(project_directory=tmp_path),
            ),
        ),
    )
    service = CandidateQualityReviewService(refs)
    return service, refs, preparation, image_path, manifest


def _snapshot(service, prep, monkeypatch):
    monkeypatch.setattr(
        "vscs.application.caps.visual_candidate_quality.prepare_visual_identity",
        lambda *_args, **_kwargs: prep,
    )
    return service.snapshot("STORY-LOC-001", 7)


def test_local_candidate_quality_snapshot_checks_review_provenance(tmp_path, monkeypatch):
    service, _refs, prep, _image, _manifest = _scenario(tmp_path)
    snap = _snapshot(service, prep, monkeypatch)
    assert snap.reference_id == 7
    assert snap.accepted_fields == prep.accepted_fields
    assert snap.deferred_fields == prep.deferred_fields


def test_technical_only_review_is_explicitly_not_semantic_pass(tmp_path, monkeypatch):
    service, refs, prep, _image, _manifest = _scenario(tmp_path)
    snap = _snapshot(service, prep, monkeypatch)
    report = service.evaluate(snap)
    assert report.semantic is None
    assert report.decision in {"SEMANTIC_REVIEW_NOT_RUN", "REGENERATE_RECOMMENDED"}
    assert any("cannot identify objects" in item for item in report.recommendations)
    saved = service.save(report)
    payload = json.loads(saved.read_text(encoding="utf-8"))
    assert payload["governance"] == "advisory_only_no_approval"
    assert payload["semantic"] is None
    assert payload["deferred_fields"] == ["lighting", "architecture"]
    refs.approve.assert_not_called()
    refs.archive.assert_not_called()
    refs.set_primary.assert_not_called()


def test_semantic_model_receives_reviewed_fields_and_deferred_context(tmp_path, monkeypatch):
    service, _refs, prep, _image, _manifest = _scenario(tmp_path)
    snap = _snapshot(service, prep, monkeypatch)
    good = SemanticMetric(name="Review", score=85, summary="No decisive contradiction.")
    model = SemanticModelResult(
        prompt_adherence=good,
        category_validity=good,
        visible_text=good,
        canon_consistency=good,
        engineering_plausibility=good,
        cinematic_quality=good,
        violations=("An additional door may be visible.",),
        recommendations=("Check the second doorway against the reviewed floor plan.",),
        summary="Plausible room; door count needs operator review.",
    )
    provider = SimpleNamespace(
        provider_name="Fake vision",
        model_name="test",
        evaluate=Mock(return_value=model),
    )
    report = service.evaluate(snap, semantic_provider=provider)
    assert report.semantic is not None
    assert report.decision != "APPROVED"
    kwargs = provider.evaluate.call_args.kwargs
    assert "A rectangular room" in kwargs["visual_identity"]
    assert "lighting" in kwargs["production_notes"]
    assert "console sits beside" in kwargs["production_notes"]
    assert "additional door" in "\n".join(report.recommendations)


def test_changed_image_is_refused_before_review(tmp_path, monkeypatch):
    service, _refs, prep, image, _manifest = _scenario(tmp_path)
    _snapshot(service, prep, monkeypatch)
    image.write_bytes(b"tampered image")
    with pytest.raises(CandidateQualityError, match="provenance"):
        service.snapshot("STORY-LOC-001", 7)


def test_stale_cap_design_refuses_report_persistence(tmp_path, monkeypatch):
    service, refs, prep, _image, _manifest = _scenario(tmp_path)
    snap = _snapshot(service, prep, monkeypatch)
    result = service.evaluate(snap)
    monkeypatch.setattr(
        "vscs.application.caps.visual_candidate_quality.prepare_visual_identity",
        lambda *_a, **_kw: replace(prep, review_fingerprint="new-review"),
    )
    with pytest.raises(CandidateQualityError, match="provenance"):
        service.save(result)
    refs.approve.assert_not_called()


def test_wrong_reference_role_is_not_evaluated(tmp_path, monkeypatch):
    service, refs, prep, _image, _manifest = _scenario(tmp_path)
    refs.get.return_value.role = CanonicalReferenceRole.PRIMARY
    monkeypatch.setattr(
        "vscs.application.caps.visual_candidate_quality.prepare_visual_identity",
        lambda *_a, **_kw: prep,
    )
    with pytest.raises(CandidateQualityError, match="supplementary"):
        service.snapshot("STORY-LOC-001", 7)


def test_candidate_quality_ui_is_read_only(qtbot, tmp_path, monkeypatch):
    service, _refs, prep, _image, _manifest = _scenario(tmp_path)
    snap = _snapshot(service, prep, monkeypatch)
    result = service.evaluate(snap)
    dialog = CandidateQualityReportDialog(result, "local.report.json")
    qtbot.addWidget(dialog)
    assert dialog.findChild(QImage, "visualCandidateQualityDetails") is None
    from PySide6.QtWidgets import QPlainTextEdit

    detail = dialog.findChild(QPlainTextEdit, "visualCandidateQualityDetails")
    assert detail is not None and detail.isReadOnly()
    assert "NON-AUTHORITATIVE" in detail.toPlainText()


def test_operator_without_candidate_is_informed(qtbot, monkeypatch):
    widget = SimpleNamespace(
        reference_gallery=SimpleNamespace(selected_reference=lambda: None),
        profile=None,
    )
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args: messages.append("info"),
    )
    _review_selected(widget)
    assert messages == ["info"]


def test_operator_cancel_never_starts_semantic_or_offline_work(qtbot, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QWidget

    from vscs.presentation.widgets import cap_visual_candidate_quality as ui

    service, refs, preparation, _image, _manifest = _scenario(tmp_path)
    snapshot = _snapshot(service, preparation, monkeypatch)
    service.snapshot = Mock(return_value=snapshot)
    service.evaluate = Mock()
    service.save = Mock()
    monkeypatch.setattr(ui, "CandidateQualityReviewService", lambda _refs: service)
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )
    widget = QWidget()
    qtbot.addWidget(widget)
    widget.reference_gallery = SimpleNamespace(selected_reference=lambda: refs.get.return_value)
    widget.profile = SimpleNamespace(asset_id=preparation.asset_id)
    widget.reference_service = refs
    _review_selected(widget)
    service.evaluate.assert_not_called()
    service.save.assert_not_called()
    refs.approve.assert_not_called()


def test_offline_review_progress_explicitly_states_no_charge(qtbot):
    from PySide6.QtWidgets import QWidget

    from vscs.presentation.widgets.automation_progress import _OperationDialog

    host = QWidget()
    qtbot.addWidget(host)
    dialog = _OperationDialog("Candidate Quality Review", "STORY-LOC-001", host, may_charge=False)
    qtbot.addWidget(dialog)
    assert "no provider charge" in dialog.status_label.text().lower()


def test_paid_review_progress_discloses_possible_charge(qtbot):
    from PySide6.QtWidgets import QWidget

    from vscs.presentation.widgets.automation_progress import _OperationDialog

    host = QWidget()
    qtbot.addWidget(host)
    dialog = _OperationDialog("Candidate Quality Review", "STORY-LOC-001", host, may_charge=True)
    qtbot.addWidget(dialog)
    assert "may incur a charge" in dialog.status_label.text()


def test_repeated_reviews_preserve_individual_audit_files(tmp_path, monkeypatch):
    service, _refs, prep, _image, _manifest = _scenario(tmp_path)
    snap = _snapshot(service, prep, monkeypatch)
    report = service.evaluate(snap)
    first = service.save(report)
    second = service.save(report)
    assert first != second
    assert first.exists() and second.exists()
    assert (
        json.loads(first.read_text(encoding="utf-8"))["report_id"]
        != json.loads(second.read_text(encoding="utf-8"))["report_id"]
    )


def test_approved_primary_is_forwarded_only_as_a_separate_comparison_image(tmp_path, monkeypatch):
    service, refs, prep, image, _manifest = _scenario(tmp_path)
    primary = image.parent / "approved_primary.png"
    primary.write_bytes(image.read_bytes())
    refs.list_for_cap.return_value = (
        refs.get.return_value,
        SimpleNamespace(
            id=19,
            reference_type=CanonicalReferenceType.IMAGE,
            role=CanonicalReferenceRole.PRIMARY,
            status=CanonicalReferenceStatus.APPROVED,
            file_path=primary.relative_to(tmp_path),
        ),
    )
    snap = _snapshot(service, prep, monkeypatch)
    assert snap.primary_reference_path == primary
    good = SemanticMetric(name="Identity", score=85, summary="Consistent appearance")
    model = SemanticModelResult(
        prompt_adherence=good,
        category_validity=good,
        visible_text=good,
        canon_consistency=good,
        engineering_plausibility=good,
        cinematic_quality=good,
        summary="Candidate has plausible geometry",
    )
    provider = SimpleNamespace(
        provider_name="Fake vision",
        model_name="test",
        evaluate=Mock(return_value=model),
    )
    report = service.evaluate(snap, semantic_provider=provider)
    assert report.semantic is not None
    assert provider.evaluate.call_args.kwargs["primary_reference_path"] == primary
