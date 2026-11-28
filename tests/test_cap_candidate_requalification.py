"""W2.5.2: offline, auditable reuse of an unchanged reviewed visual Candidate."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps.candidate_requalification import (
    CandidateRequalificationError,
    CandidateRequalificationService,
)
from vscs.application.caps.design_revision import REVISION_HISTORY_KEY
from vscs.application.caps.structured_specification import CAPStructuredSpecification
from vscs.application.caps.visual_candidate_quality import (
    CandidateQualityError,
    CandidateQualityReviewService,
)
from vscs.application.caps.visual_identity_preparation import VisualIdentityPreparation
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import (
    CanonicalReferenceRole,
    CanonicalReferenceStatus,
    CanonicalReferenceType,
    CAPStatus,
)


def _scenario(tmp_path, monkeypatch):
    asset_id = "CAP-PRP-001"
    image_dir = tmp_path / "Canonical Assets" / asset_id / "Images" / "Visual Candidates"
    image_dir.mkdir(parents=True)
    image = image_dir / "workstation.png"
    content = b"\x89PNG\r\n\x1a\noriginal-image-data"
    image.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    old_spec = CAPStructuredSpecification(
        asset_id=asset_id,
        category=AssetCategory.PROP,
        design_intent="Maintenance workstation",
        master_prompt="Proposed image",
        canonical_attributes={"components": "chamfered corners"},
    )
    audit = {"version": 1, "reviewer": "Neill", "image_authorized": False}
    audit_hash = hashlib.sha256(
        json.dumps(audit, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest_dir = tmp_path / "Canonical Assets" / asset_id / ".metadata" / "visual"
    manifest_dir.mkdir(parents=True)
    original_manifest = {
        "asset_id": asset_id,
        "image_sha256": digest,
        "specification_fingerprint": old_spec.fingerprint(),
        "review_fingerprint": audit_hash,
        "governance": "non-authoritative_candidate_not_MASTER",
        "prompt": "Original generation prompt",
    }
    original_path = manifest_dir / "workstation.json"
    original_path.write_text(json.dumps(original_manifest))
    cap = SimpleNamespace(
        id=5,
        asset_id=asset_id,
        title="Maintenance workstation",
        version="1.0",
        status=CAPStatus.DRAFT,
        production_metadata={
            REVISION_HISTORY_KEY: json.dumps(
                [
                    {
                        "field": "components",
                        "old_value": "chamfered corners",
                        "new_value": "square corners",
                        "previous_specification": old_spec.model_dump(mode="json"),
                        "previous_review_audit": audit,
                    }
                ]
            )
        },
    )
    source = SimpleNamespace(
        id=9,
        cap_id=5,
        reference_type=CanonicalReferenceType.IMAGE,
        role=CanonicalReferenceRole.SUPPLEMENTARY,
        status=CanonicalReferenceStatus.CANDIDATE,
        locked=False,
        file_path=image.relative_to(tmp_path),
        description="Original generation prompt",
    )
    refs = SimpleNamespace(
        caps=SimpleNamespace(
            get=Mock(return_value=cap),
            assets=SimpleNamespace(projects=SimpleNamespace(project_directory=tmp_path)),
        ),
        get=Mock(return_value=source),
        create=Mock(return_value=SimpleNamespace(id=10)),
        mark_candidate=Mock(),
        delete=Mock(),
    )
    preparation = VisualIdentityPreparation(
        asset_id=asset_id,
        title=cap.title,
        category=AssetCategory.PROP,
        specification_fingerprint="current-reviewed-specification",
        review_fingerprint="current-review-audit",
        accepted_fields=(("components", "square corners"),),
        deferred_fields=(),
        continuity_context=(),
        dependency_asset_ids=(),
        blockers=(),
        master_candidate_prompt="Current reviewed square-corner design",
        negative_prompt="",
        required_reference_views=(),
        missing_reference_views=(),
    )
    monkeypatch.setattr(
        "vscs.application.caps.candidate_requalification.prepare_visual_identity",
        lambda *_args: preparation,
    )
    return CandidateRequalificationService(refs), refs, image, original_path


def test_requalification_creates_new_candidate_without_changing_original(tmp_path, monkeypatch):
    service, refs, image, manifest = _scenario(tmp_path, monkeypatch)
    image_before, manifest_before = image.read_bytes(), manifest.read_bytes()
    plan = service.prepare("CAP-PRP-001", 9)
    assert plan.changed_fields == ("components",)
    assert service.accept(plan, "Neill Payne", "Human acceptance of square corners") == 10
    new_reference = refs.create.call_args.args[1]
    assert new_reference.role is CanonicalReferenceRole.SUPPLEMENTARY
    assert "no generation" in new_reference.notes
    assert (tmp_path / new_reference.file_path).read_bytes() == image_before
    new_manifest = json.loads(
        (
            tmp_path
            / "Canonical Assets"
            / "CAP-PRP-001"
            / ".metadata"
            / "visual"
            / f"{new_reference.file_path.stem}.json"
        ).read_text()
    )
    assert new_manifest["specification_fingerprint"] == "current-reviewed-specification"
    assert new_manifest["requalification"]["source_reference_id"] == 9
    assert new_manifest["requalification"]["no_image_generation"] is True
    assert image.read_bytes() == image_before
    assert manifest.read_bytes() == manifest_before
    refs.mark_candidate.assert_called_once_with(10)


def test_cancel_or_stale_review_never_creates_candidate(tmp_path, monkeypatch):
    service, refs, _image, _manifest = _scenario(tmp_path, monkeypatch)
    plan = service.prepare("CAP-PRP-001", 9)
    with pytest.raises(CandidateRequalificationError, match="Reviewer and rationale"):
        service.accept(plan, "", "")
    changed = plan.__class__(**{**plan.__dict__, "current_review_fingerprint": "stale"})
    with pytest.raises(CandidateRequalificationError, match="changed"):
        service.accept(changed, "Neill", "Human accepts revised corners")
    refs.create.assert_not_called()


def test_changed_image_or_unrelated_history_fails_closed(tmp_path, monkeypatch):
    service, refs, image, _manifest = _scenario(tmp_path, monkeypatch)
    image.write_bytes(image.read_bytes() + b"changed")
    with pytest.raises(CandidateRequalificationError, match="inconsistent"):
        service.prepare("CAP-PRP-001", 9)
    refs.create.assert_not_called()


def test_new_candidate_passes_current_quality_provenance_and_old_one_does_not(
    tmp_path, monkeypatch
):
    service, refs, image, old_manifest = _scenario(tmp_path, monkeypatch)
    plan = service.prepare("CAP-PRP-001", 9)
    service.accept(plan, "Neill", "Verified same image against revised design")
    new_input = refs.create.call_args.args[1]
    new_reference = SimpleNamespace(
        id=10,
        cap_id=5,
        file_path=new_input.file_path,
        description=new_input.description,
        reference_type=CanonicalReferenceType.IMAGE,
        role=CanonicalReferenceRole.SUPPLEMENTARY,
        status=CanonicalReferenceStatus.CANDIDATE,
        locked=False,
    )
    source = refs.get.return_value
    refs.get.side_effect = lambda reference_id: new_reference if reference_id == 10 else source
    refs.list_for_cap = Mock(return_value=(source, new_reference))
    refs.caps.assets.get = Mock(
        return_value=SimpleNamespace(
            asset_id="CAP-PRP-001",
            name="Maintenance workstation",
            category=AssetCategory.PROP,
        )
    )
    monkeypatch.setattr(
        "vscs.application.caps.visual_candidate_quality.prepare_visual_identity",
        lambda *_args: VisualIdentityPreparation(
            asset_id="CAP-PRP-001",
            title="Maintenance workstation",
            category=AssetCategory.PROP,
            specification_fingerprint=plan.current_specification_fingerprint,
            review_fingerprint=plan.current_review_fingerprint,
            accepted_fields=(("components", "square corners"),),
            deferred_fields=(),
            continuity_context=(),
            dependency_asset_ids=(),
            blockers=(),
            master_candidate_prompt=plan.current_prompt,
            negative_prompt="",
            required_reference_views=(),
            missing_reference_views=(),
        ),
    )
    reviewer = CandidateQualityReviewService(refs)
    with pytest.raises(CandidateQualityError, match="provenance has changed"):
        reviewer.snapshot("CAP-PRP-001", 9)
    assert reviewer.snapshot("CAP-PRP-001", 10).reference_id == 10
    old_manifest.write_text('{"tampered":true}')
    with pytest.raises(CandidateQualityError, match="Original Candidate provenance"):
        reviewer.snapshot("CAP-PRP-001", 10)
    assert image.is_file()
