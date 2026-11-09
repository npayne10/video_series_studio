"""B.5.26F: register a reviewed guided-edit output as Candidate only.

This service is deliberately separate from ComfyUI submission. UI consent,
source provenance and CAP authority must still hold at registration time.
"""

from __future__ import annotations

import hashlib

from vscs.application.caps.guided_edit_live_transport import GuidedEditOutput
from vscs.application.caps.spatial_correction_contract import (
    SpatialCorrectionContract,
    verify_spatial_contract,
)
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)
from vscs.domain.caps import GeneratedCanonicalAsset


class GuidedEditRegistrationError(RuntimeError):
    """Guided output is not a currently authorized supplementary Candidate."""


def register_guided_edit_candidate(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
    output: GuidedEditOutput,
    *,
    operator_confirmed: bool,
) -> int:
    """Register one valid result, without Canon or MASTER approval.

    Call only from the operator-approved GUI thread, after the ComfyUI
    history and exact output node have been verified. No generation here.
    """
    if operator_confirmed is not True:
        raise GuidedEditRegistrationError("Explicit operator confirmation is required")
    verify_spatial_contract(service, plan, contract)
    if (
        output.contract_sha256 != contract.evidence_sha256
        or output.workflow_sha256 != contract.workflow_sha256
        or not output.prompt_id
        or not output.output_node_id
        or not output.filename
    ):
        raise GuidedEditRegistrationError("Guided output provenance is stale or incomplete")
    if (
        not output.content.startswith(b"\x89PNG\r\n\x1a\n")
        or hashlib.sha256(output.content).hexdigest() != output.image_sha256
        or output.image_sha256 == contract.source_sha256
    ):
        raise GuidedEditRegistrationError("Guided output is invalid or unchanged from source")
    if not 256 <= output.width <= 8192 or not 256 <= output.height <= 8192:
        raise GuidedEditRegistrationError("Guided output dimensions are outside CAP limits")
    if contract.correction_attempt != plan.attempt or not 1 <= plan.attempt <= 2:
        raise GuidedEditRegistrationError("Correction attempt lineage is inconsistent")
    request = plan.request.model_copy(
        update={
            "model": "XCIC / local ComfyUI Qwen-Image-Edit-2511",
            "width": output.width,
            "height": output.height,
            "variations": 1,
        }
    )
    generated = GeneratedCanonicalAsset(
        filename=output.filename,
        media_type="image/png",
        content=output.content,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        model=request.model,
        seed=request.seed,
        width=request.width,
        height=request.height,
    )
    lineage = {
        **plan.lineage,
        "guided_edit_contract_sha256": contract.evidence_sha256,
        "guided_edit_workflow_sha256": contract.workflow_sha256,
        "guided_edit_output_sha256": output.image_sha256,
        "guided_edit_prompt_id": output.prompt_id,
        "guided_edit_source_sha256": contract.source_sha256,
        "guided_edit_model_identifier": contract.model_identifier,
    }
    if contract.mask_sha256 is not None:
        lineage["guided_edit_mask_sha256"] = contract.mask_sha256
    # Do not bypass the existing CAP Candidate persistence revalidation.
    # A successful call consumes one governed correction attempt.
    return service.generator.persist_candidate(
        plan.preparation,
        plan.source.project_root,
        request,
        generated,
        regeneration=lineage,
    )
