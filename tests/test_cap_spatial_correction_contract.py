"""B.5.26F F3: offline spatial contract and tamper resistance."""

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps.spatial_correction_contract import (
    SpatialCorrectionContractError,
    prepare_spatial_contract,
    verify_spatial_contract,
)
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot
from vscs.application.caps.visual_identity_preparation import VisualIdentityPreparation
from vscs.domain.assets.models import AssetCategory
from vscs.domain.caps import CanonicalAssetGenerationRequest


def _fixture(tmp_path):
    asset = "STORY-LOC-001"
    candidate_dir = (
        tmp_path / "Canonical Assets" / asset / "Images" / "Visual Candidates"
    )
    candidate_dir.mkdir(parents=True)
    source = candidate_dir / "room.png"
    Image.new("RGB", (16, 12), "gray").save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    accepted = (("layout", "Exactly one access door."),)
    prep = VisualIdentityPreparation(
        asset_id=asset,
        title="Room",
        category=AssetCategory.LOCATION,
        specification_fingerprint="spec1",
        review_fingerprint="rev1",
        accepted_fields=accepted,
        deferred_fields=(),
        continuity_context=(),
        dependency_asset_ids=(),
        blockers=(),
        master_candidate_prompt="A room",
        negative_prompt="no extra doors",
        required_reference_views=(),
        missing_reference_views=(),
    )
    snapshot = CandidateQualitySnapshot(
        asset_id=asset,
        asset_name="Room",
        category=AssetCategory.LOCATION,
        reference_id=2,
        project_root=tmp_path,
        image_path=source,
        image_sha256=digest,
        primary_reference_path=None,
        specification_fingerprint="spec1",
        review_fingerprint="rev1",
        accepted_fields=accepted,
        deferred_fields=(),
        continuity=(),
        dependencies=(),
        generation_prompt="A room",
        reference_role="supplementary",
        reference_status="candidate",
    )
    report_dir = tmp_path / "Canonical Assets" / asset / ".metadata" / "evaluation"
    report_dir.mkdir(parents=True)
    report = report_dir / "review.candidate_quality.json"
    report.write_text('{"semantic":{"decision":"regenerate"}}', encoding="utf-8")
    plan = CandidateRegenerationPlan(
        preparation=prep,
        source=snapshot,
        report_path=report,
        report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
        original_reference_id=1,
        attempt=2,
        max_attempts=2,
        request=CanonicalAssetGenerationRequest(prompt="Correct only one door"),
        correction_rules=("MANDATORY layout: exactly one door",),
        review_findings=("Extra door found",),
        previous_technical_score=79,
        previous_semantic_score=58,
        effectiveness_warnings=("semantic quality -14",),
    )
    workflow_dir = tmp_path / "XCIC" / "workflows"
    workflow_dir.mkdir(parents=True)
    workflow = workflow_dir / "edit_api.json"
    workflow.write_text(
        json.dumps({"1": {"class_type": "LoadImage", "inputs": {"image": "source.png"}}}),
        encoding="utf-8",
    )
    mask_dir = tmp_path / "Canonical Assets" / asset / ".metadata" / "spatial_masks"
    mask_dir.mkdir(parents=True)
    mask = mask_dir / "door.png"
    Image.new("L", (16, 12), 0).save(mask)
    service = SimpleNamespace(verify_current=Mock())
    return service, plan, workflow_dir, workflow, mask


def _prepare(service, plan, workflow_dir, workflow, mask=None):
    return prepare_spatial_contract(
        service,
        plan,
        workflow_path=workflow,
        trusted_workflow_directory=workflow_dir,
        workflow_id="qwen.image.edit.2511",
        model_identifier="qwen_image_edit_2511_fp8mixed",
        mask_path=mask,
    )


def test_f3_seals_evidence_and_revalidates_without_provider_execution(tmp_path):
    service, plan, folder, workflow, mask = _fixture(tmp_path)
    contract = _prepare(service, plan, folder, workflow, mask)
    assert contract.source_reference_id == 2
    assert contract.original_reference_id == 1
    assert contract.correction_attempt == 2
    assert contract.mask_sha256 is not None
    assert len(contract.evidence_sha256) == 64
    assert not contract.execution_authorized
    verify_spatial_contract(service, plan, contract)
    assert service.verify_current.call_count == 2


@pytest.mark.parametrize("tamper", ["source", "mask", "workflow", "report"])
def test_f3_detects_changed_evidence(tmp_path, tamper):
    service, plan, folder, workflow, mask = _fixture(tmp_path)
    contract = _prepare(service, plan, folder, workflow, mask)
    path = {
        "source": plan.source.image_path,
        "mask": mask,
        "workflow": workflow,
        "report": plan.report_path,
    }[tamper]
    path.write_bytes(b"changed evidence")
    with pytest.raises(SpatialCorrectionContractError, match="changed"):
        verify_spatial_contract(service, plan, contract)


def test_f3_detects_contract_field_tampering(tmp_path):
    service, plan, folder, workflow, mask = _fixture(tmp_path)
    contract = _prepare(service, plan, folder, workflow, mask)
    forged = replace(contract, model_identifier="unapproved model")
    with pytest.raises(SpatialCorrectionContractError, match="seal changed"):
        verify_spatial_contract(service, plan, forged)


def test_f3_rejects_mask_from_other_asset(tmp_path):
    service, plan, folder, workflow, _mask = _fixture(tmp_path)
    other = tmp_path / "Canonical Assets" / "OTHER" / ".metadata" / "spatial_masks"
    other.mkdir(parents=True)
    mask = other / "door.png"
    Image.new("L", (16, 12), 0).save(mask)
    with pytest.raises(SpatialCorrectionContractError, match="escaped"):
        _prepare(service, plan, folder, workflow, mask)


@pytest.mark.parametrize("mode,dimensions", [("RGB", (16, 12)), ("L", (20, 12))])
def test_f3_rejects_invalid_mask_semantics(tmp_path, mode, dimensions):
    service, plan, folder, workflow, mask = _fixture(tmp_path)
    Image.new(mode, dimensions, 0).save(mask)
    with pytest.raises(SpatialCorrectionContractError, match="8-bit grayscale"):
        _prepare(service, plan, folder, workflow, mask)


def test_f3_allows_no_mask_but_never_authorizes_generation(tmp_path):
    service, plan, folder, workflow, _mask = _fixture(tmp_path)
    contract = _prepare(service, plan, folder, workflow)
    assert contract.mask_path is None
    assert contract.mask_sha256 is None
    assert not contract.execution_authorized


def test_f3_blocks_mismatched_cap_fingerprint(tmp_path):
    service, plan, folder, workflow, _mask = _fixture(tmp_path)
    changed = replace(plan, preparation=replace(plan.preparation, review_fingerprint="rev2"))
    with pytest.raises(SpatialCorrectionContractError, match="authority"):
        _prepare(service, changed, folder, workflow)


def test_f3_blocks_unbounded_attempt(tmp_path):
    service, plan, folder, workflow, _mask = _fixture(tmp_path)
    changed = replace(plan, attempt=3)
    with pytest.raises(SpatialCorrectionContractError, match="bounded"):
        _prepare(service, changed, folder, workflow)


def test_f3_rejects_workflow_outside_trusted_directory(tmp_path):
    service, plan, folder, _workflow, _mask = _fixture(tmp_path)
    external = tmp_path / "untrusted.json"
    external.write_text('{"1":{"class_type":"LoadImage","inputs":{}}}', encoding="utf-8")
    with pytest.raises(SpatialCorrectionContractError, match="escaped"):
        _prepare(service, plan, folder, external)


def test_f3_blocks_stale_authority_before_accessing_provider(tmp_path):
    service, plan, folder, workflow, _mask = _fixture(tmp_path)
    service.verify_current.side_effect = RuntimeError("CAP changed")
    with pytest.raises(RuntimeError, match="CAP changed"):
        _prepare(service, plan, folder, workflow)
    assert not workflow.with_suffix(".output").exists()
