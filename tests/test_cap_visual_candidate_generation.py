"""B.5.26 local image candidate generation without MASTER or production approval."""

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.visual_candidate_generation import (
    VisualCandidateGenerationError,
    VisualCandidateGenerationService,
)
from vscs.application.caps.visual_identity_preparation import VisualIdentityPreparation
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalReferenceRole,
    CanonicalReferenceView,
    GeneratedCanonicalAsset,
)
from vscs.presentation.widgets.cap_visual_identity_preparation import (
    VisualIdentityPreparationDialog,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"test-candidate"


def _prep(*, blockers=()):
    return VisualIdentityPreparation(
        asset_id="STORY-LOC-001",
        title="Engineering control room",
        category=AssetCategory.LOCATION,
        specification_fingerprint="story-spec-v1",
        review_fingerprint="review-v1",
        accepted_fields=(("layout", "Rectangular room"),),
        deferred_fields=("lighting",),
        continuity_context=(),
        dependency_asset_ids=(),
        blockers=blockers,
        master_candidate_prompt="PROPOSED MASTER REFERENCE CANDIDATE: rectangular room.",
        negative_prompt="no unreviewed geometry",
        required_reference_views=(CanonicalReferenceView.MASTER,),
        missing_reference_views=(CanonicalReferenceView.MASTER,),
    )


def _service(tmp_path: Path, preparation: VisualIdentityPreparation, *, content=PNG):
    output = GeneratedCanonicalAsset(
        filename="from_provider.png",
        content=content,
        media_type="image/png",
        model="Local XCIC test",
        prompt=preparation.master_candidate_prompt,
        negative_prompt=preparation.negative_prompt,
        width=1280,
        height=720,
        seed=5,
    )
    provider = SimpleNamespace(generate_images=Mock(return_value=(output,)))
    cap = SimpleNamespace(id=7, asset_id=preparation.asset_id, title=preparation.title, version="1.0")
    refs = SimpleNamespace(
        caps=SimpleNamespace(
            get=Mock(return_value=cap),
            assets=SimpleNamespace(projects=SimpleNamespace(project_directory=tmp_path)),
        ),
        create=Mock(return_value=SimpleNamespace(id=77)),
        mark_candidate=Mock(),
        delete=Mock(),
    )
    service = object.__new__(VisualCandidateGenerationService)
    service.references = refs
    service.provider_factory = lambda _path: provider
    service.prepare = lambda _asset_id: preparation
    return service, refs, provider


def test_blocked_ship_never_invokes_local_provider(tmp_path):
    prep = replace(_prep(), blockers=("Ship silhouette is deferred",))
    service, refs, provider = _service(tmp_path, prep)
    with pytest.raises(VisualCandidateGenerationError, match="blocked"):
        service.generate(prep.asset_id)
    provider.generate_images.assert_not_called()
    refs.create.assert_not_called()


def test_local_candidate_is_saved_only_as_supplementary_candidate(tmp_path):
    prep = _prep()
    service, refs, provider = _service(tmp_path, prep)
    reference_id = service.generate(prep.asset_id, seed=5)
    assert reference_id == 77
    assert provider.generate_images.call_count == 1
    refs.create.assert_called_once()
    value = refs.create.call_args.args[1]
    assert value.role is CanonicalReferenceRole.SUPPLEMENTARY
    assert "NOT a ChatGPT MASTER" in value.notes
    refs.mark_candidate.assert_called_once_with(77)
    image = tmp_path / value.file_path
    assert image.read_bytes() == PNG
    manifests = list(tmp_path.rglob("*.json"))
    assert len(manifests) == 1
    details = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert details["governance"] == "non-authoritative_candidate_not_MASTER"
    assert details["specification_fingerprint"] == prep.specification_fingerprint
    assert details["review_fingerprint"] == prep.review_fingerprint


def test_rejected_non_png_cannot_create_reference(tmp_path):
    prep = _prep()
    service, refs, _provider = _service(tmp_path, prep, content=b"not an image")
    with pytest.raises(VisualCandidateGenerationError, match="PNG"):
        service.generate(prep.asset_id)
    refs.create.assert_not_called()
    assert list(tmp_path.rglob("*.png")) == []


def test_changed_review_before_persistence_fails_closed(tmp_path):
    prep = _prep()
    service, refs, _provider = _service(tmp_path, prep)
    project, request = service.prepare_request(prep)
    image = service.render(prep, project, request)
    service.prepare = lambda _asset_id: replace(prep, review_fingerprint="changed")
    with pytest.raises(VisualCandidateGenerationError, match="changed"):
        service.persist_candidate(prep, project, request, image)
    refs.create.assert_not_called()
    assert list(tmp_path.rglob("*.png")) == []


def test_blocked_visual_candidate_button_is_disabled(qtbot):
    service = Mock()
    dialog = VisualIdentityPreparationDialog(
        replace(_prep(), blockers=("Unresolved silhouette",)), service
    )
    qtbot.addWidget(dialog)
    assert not dialog.generate_button.isEnabled()
    assert dialog.prompt_view.isReadOnly()


def test_ready_visual_candidate_button_requires_explicit_operator_action(qtbot):
    service = Mock()
    dialog = VisualIdentityPreparationDialog(_prep(), service)
    qtbot.addWidget(dialog)
    assert dialog.generate_button.isEnabled()
    service.render.assert_not_called()


def test_operator_declines_local_generation_without_calling_provider(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    service = Mock()
    dialog = VisualIdentityPreparationDialog(_prep(), service)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args, **_kw: QMessageBox.StandardButton.No
    )
    dialog._generate_local()
    service.prepare_request.assert_not_called()
    service.render.assert_not_called()
    service.persist_candidate.assert_not_called()


def test_operator_confirmation_uses_progress_before_gui_persistence(
    qtbot, monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QMessageBox

    from vscs.presentation.widgets.automation_progress import AutomationProgressRunner

    preparation = _prep()
    service = Mock()
    request = SimpleNamespace(prompt=preparation.master_candidate_prompt)
    service.prepare_request.return_value = (tmp_path, request)
    render_result = object()
    events = []

    def run(_runner, _title, _asset_id, operation):
        events.append("render")
        assert operation() is render_result
        return render_result

    def persist(*_args):
        events.append("persist")
        return 77

    service.render.return_value = render_result
    service.persist_candidate.side_effect = persist
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args, **_kw: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kw: None)
    monkeypatch.setattr(AutomationProgressRunner, "run", run)

    dialog = VisualIdentityPreparationDialog(preparation, service)
    qtbot.addWidget(dialog)
    dialog._generate_local()
    assert events == ["render", "persist"]
    service.persist_candidate.assert_called_once_with(
        preparation, tmp_path, request, render_result
    )
    assert dialog.result() == dialog.DialogCode.Accepted
