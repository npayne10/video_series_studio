"""F4B2: register only validated guided outputs as supplementary Candidates."""

import hashlib
import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import guided_edit_candidate_registration as registration


def _setup():
    image = io.BytesIO()
    Image.new("RGB", (512, 512), "gray").save(image, format="PNG")
    data = image.getvalue()
    source = b"original image bytes"
    output = SimpleNamespace(
        content=data,
        image_sha256=hashlib.sha256(data).hexdigest(),
        width=512,
        height=512,
        prompt_id="once-only-id",
        output_node_id="9",
        filename="edited.png",
        workflow_sha256="workflow-hash",
        contract_sha256="contract-hash",
    )
    request = SimpleNamespace(
        prompt="approved fields",
        negative_prompt="no extra doors",
        seed=3,
    )
    request.model_copy = Mock(
        side_effect=lambda update: SimpleNamespace(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            seed=request.seed,
            model=update["model"],
            width=update["width"],
            height=update["height"],
        )
    )
    plan = SimpleNamespace(
        attempt=2,
        preparation=SimpleNamespace(),
        request=request,
        lineage={"original_reference_id": 1, "parent_reference_id": 2, "attempt": 2},
        source=SimpleNamespace(project_root="/tmp/project"),
    )
    contract = SimpleNamespace(
        evidence_sha256="contract-hash",
        workflow_sha256="workflow-hash",
        source_sha256=hashlib.sha256(source).hexdigest(),
        mask_sha256=None,
        correction_attempt=2,
        model_identifier="qwen_image_edit_2511_fp8mixed",
    )
    service = SimpleNamespace(generator=SimpleNamespace(persist_candidate=Mock(return_value=42)))
    return service, plan, contract, output


def test_f4b2_valid_output_is_candidate_only(monkeypatch):
    service, plan, contract, output = _setup()
    verification = Mock()
    monkeypatch.setattr(registration, "verify_spatial_contract", verification)
    assert (
        registration.register_guided_edit_candidate(
            service, plan, contract, output, operator_confirmed=True
        )
        == 42
    )
    verification.assert_called_once_with(service, plan, contract)
    service.generator.persist_candidate.assert_called_once()
    _, _, request, generated = service.generator.persist_candidate.call_args.args
    assert request.model == "XCIC / local ComfyUI Qwen-Image-Edit-2511"
    assert generated.content == output.content
    lineage = service.generator.persist_candidate.call_args.kwargs["regeneration"]
    assert lineage["guided_edit_output_sha256"] == output.image_sha256
    assert lineage["guided_edit_prompt_id"] == output.prompt_id
    assert lineage["attempt"] == 2


def test_f4b2_registration_denied_without_consent(monkeypatch):
    service, plan, contract, output = _setup()
    verification = Mock()
    monkeypatch.setattr(registration, "verify_spatial_contract", verification)
    with pytest.raises(registration.GuidedEditRegistrationError, match="confirmation"):
        registration.register_guided_edit_candidate(
            service, plan, contract, output, operator_confirmed=False
        )
    verification.assert_not_called()
    service.generator.persist_candidate.assert_not_called()


@pytest.mark.parametrize("field", ["contract_sha256", "workflow_sha256", "prompt_id"])
def test_f4b2_registration_denied_on_stale_output(monkeypatch, field):
    service, plan, contract, output = _setup()
    monkeypatch.setattr(registration, "verify_spatial_contract", Mock())
    setattr(output, field, "unexpected" if field != "prompt_id" else "")
    with pytest.raises(registration.GuidedEditRegistrationError, match="provenance"):
        registration.register_guided_edit_candidate(
            service, plan, contract, output, operator_confirmed=True
        )
    service.generator.persist_candidate.assert_not_called()


def test_f4b2_registration_refuses_tampered_image(monkeypatch):
    service, plan, contract, output = _setup()
    monkeypatch.setattr(registration, "verify_spatial_contract", Mock())
    output.content = b"forged image"
    with pytest.raises(registration.GuidedEditRegistrationError, match="invalid"):
        registration.register_guided_edit_candidate(
            service, plan, contract, output, operator_confirmed=True
        )
    service.generator.persist_candidate.assert_not_called()


def test_f4b2_registration_refuses_exhausted_lineage(monkeypatch):
    service, plan, contract, output = _setup()
    monkeypatch.setattr(registration, "verify_spatial_contract", Mock())
    plan.attempt = 3
    with pytest.raises(registration.GuidedEditRegistrationError, match="lineage"):
        registration.register_guided_edit_candidate(
            service, plan, contract, output, operator_confirmed=True
        )
    service.generator.persist_candidate.assert_not_called()


def test_f4b2_registration_authority_failure_never_writes(monkeypatch):
    service, plan, contract, output = _setup()
    monkeypatch.setattr(
        registration,
        "verify_spatial_contract",
        Mock(side_effect=RuntimeError("CAP changed")),
    )
    with pytest.raises(RuntimeError, match="CAP changed"):
        registration.register_guided_edit_candidate(
            service, plan, contract, output, operator_confirmed=True
        )
    service.generator.persist_candidate.assert_not_called()
