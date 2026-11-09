"""B.5.26F: one explicitly confirmed managed Qwen CAP correction render.

This adapter uses the existing reference-conditioned Qwen Image Edit v2.1
graph and XCICQwenReferenceJobLoader. A network submission can only happen
after current CAP verification, installed-node validation and a durable
once-only reservation. It never registers a Candidate or approves Canon.
"""

from __future__ import annotations

import hashlib
import json
import time
from uuid import uuid4

from vscs.application.caps.guided_edit_attempt_journal import reserve_guided_edit_attempt
from vscs.application.caps.guided_edit_live_transport import (
    GuidedEditExecutionError,
    GuidedEditOutput,
    _checked_png,
    _loopback_endpoint,
)
from vscs.application.caps.managed_qwen_correction_job import (
    prepare_managed_qwen_correction,
)
from vscs.application.caps.spatial_correction_contract import (
    SpatialCorrectionContract,
    verify_spatial_contract,
)
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)
from vscs.infrastructure.xcic_core.client import XCICCoreClient

_MAX_OUTPUT_BYTES = 40 * 1024 * 1024


def render_one_managed_qwen_correction(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
    *,
    operator_confirmed: bool,
    comfyui_url: str = "http://127.0.0.1:8188",
    timeout_seconds: float = 3600.0,
    client: XCICCoreClient | None = None,
) -> GuidedEditOutput:
    """Submit exactly one model edit, keeping the output non-authoritative.

    A POST timeout has an unknown outcome: the durable reservation remains.
    Never automatically retry after this method raises.
    """
    if operator_confirmed is not True:
        raise GuidedEditExecutionError("Explicit operator approval required before Qwen editing")
    base = _loopback_endpoint(comfyui_url)
    if not 1 <= timeout_seconds <= 7200:
        raise GuidedEditExecutionError("Invalid Qwen correction timeout")
    verify_spatial_contract(service, plan, contract)
    if contract.mask_path is not None:
        raise GuidedEditExecutionError("Masked corrections require a separately verified graph")
    job_id = uuid4().hex
    runtime = contract.project_root / ".vscs" / "runtime" / "comfyui"
    queue_path = runtime / "queues" / f"cap_correction_{job_id}.json"
    output_root = runtime / "jobs" / job_id / "output"
    output_path = output_root / f"cap_correction_{job_id}.png"
    job = prepare_managed_qwen_correction(
        service,
        plan,
        contract,
        workflow_path=contract.workflow_path,
        queue_path=queue_path,
        output_path=output_path,
        job_id=job_id,
    )
    provider = client if client is not None else XCICCoreClient(base)
    # Read-only network validation happens BEFORE the attempt reservation.
    provider.healthcheck()
    provider.validate_nodes(job.workflow)
    verify_spatial_contract(service, plan, contract)
    # Preserve uncertainty even if queue writing or network transport fails.
    reserve_guided_edit_attempt(contract)
    for directory in (queue_path.parent, output_root):
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise GuidedEditExecutionError("Managed Qwen runtime directory is unsafe")
    with queue_path.open("x", encoding="utf-8") as stream:
        json.dump(job.queue, stream, indent=2, sort_keys=True)
        stream.flush()
    # F3 authority must still hold immediately before a possible POST.
    verify_spatial_contract(service, plan, contract)
    prompt_id = provider.submit(job.workflow)
    history = provider.wait(prompt_id, timeout_seconds=timeout_seconds)
    if not isinstance(history, dict):
        raise GuidedEditExecutionError("ComfyUI returned invalid prompt history")
    deadline = time.monotonic() + 15.0
    while not output_path.is_file() and time.monotonic() < deadline:
        time.sleep(0.25)
    if not output_path.is_file() or output_path.is_symlink():
        raise GuidedEditExecutionError("Expected isolated Qwen output was not written")
    with output_path.open("rb") as stream:
        content = stream.read(_MAX_OUTPUT_BYTES + 1)
    width, height = _checked_png(content, maximum_bytes=_MAX_OUTPUT_BYTES)
    if width < 256 or height < 256:
        raise GuidedEditExecutionError("Qwen output is smaller than CAP Candidate limits")
    verify_spatial_contract(service, plan, contract)
    return GuidedEditOutput(
        content=content,
        image_sha256=hashlib.sha256(content).hexdigest(),
        width=width,
        height=height,
        prompt_id=prompt_id,
        output_node_id="9",
        filename=output_path.name,
        workflow_sha256=job.workflow_sha256,
        contract_sha256=contract.evidence_sha256,
        executed_prompt=str(job.queue["jobs"][0]["positive_prompt"]),
    )
