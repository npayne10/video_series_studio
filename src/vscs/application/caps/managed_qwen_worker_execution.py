"""Thread-safe transport for a GUI-prepared managed Qwen CAP correction job.

Only immutable file evidence and the ComfyUI transport are touched in
the QThread. CAP/database authority must be checked on the GUI thread
immediately before this call and again before Candidate registration.
"""

from __future__ import annotations

import copy
import hashlib
import json
import time
from pathlib import Path

from vscs.application.caps.guided_edit_attempt_journal import reserve_guided_edit_attempt
from vscs.application.caps.guided_edit_live_transport import (
    GuidedEditExecutionError,
    GuidedEditOutput,
    _checked_png,
    _loopback_endpoint,
)
from vscs.application.caps.managed_qwen_correction_job import (
    ManagedQwenCorrectionJob,
    managed_qwen_positive_prompt,
)
from vscs.application.caps.managed_qwen_model_inventory import (
    validate_managed_qwen_model_choices,
)
from vscs.application.caps.spatial_correction_contract import SpatialCorrectionContract
from vscs.infrastructure.xcic_core.client import XCICCoreClient

_MAX_BYTES = 40 * 1024 * 1024


def _unchanged(contract: SpatialCorrectionContract, job: ManagedQwenCorrectionJob) -> None:
    """Recheck immutable evidence only; never open CAP/SQLite in the worker."""
    contract.verify_seal()
    if (
        job.contract_sha256 != contract.evidence_sha256
        or job.workflow_sha256 != contract.workflow_sha256
        or job.source_sha256 != contract.source_sha256
    ):
        raise GuidedEditExecutionError("Prepared Qwen edit authority changed")
    for path, expected in (
        (contract.workflow_path, contract.workflow_sha256),
        (contract.source_path, contract.source_sha256),
        (contract.quality_report_path, contract.quality_report_sha256),
    ):
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise GuidedEditExecutionError("Qwen edit evidence changed after operator approval")
    human_path = getattr(contract, "human_disposition_path", None)
    human_sha = getattr(contract, "human_disposition_sha256", None)
    if human_path is not None and (
        not isinstance(human_sha, str)
        or not human_path.is_file()
        or human_path.is_symlink()
        or hashlib.sha256(human_path.read_bytes()).hexdigest() != human_sha
    ):
        raise GuidedEditExecutionError("Reviewer correction disposition changed after preparation")
    jobs = job.queue.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 1 or not isinstance(jobs[0], dict):
        raise GuidedEditExecutionError("Managed edit must contain exactly one queue job")
    item = jobs[0]
    output = item.get("output")
    human_field: str | None = None
    if human_path is not None:
        try:
            record = json.loads(human_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise GuidedEditExecutionError("Reviewer decision cannot be read") from exc
        if not isinstance(record, dict) or not isinstance(record.get("accepted_field"), str):
            raise GuidedEditExecutionError("Reviewer decision field is malformed")
        human_field = record["accepted_field"]
    prompt = managed_qwen_positive_prompt(contract.accepted_fields, human_field)
    if (
        item.get("reference_inputs") != [str(contract.source_path)]
        or item.get("positive_prompt") != prompt
        or not isinstance(output, dict)
        or output.get("candidate_directory") != str(job.output_path.parent)
        or output.get("candidate_filename") != job.output_path.name
        or type(item.get("seed")) is not int
    ):
        raise GuidedEditExecutionError("Prepared Qwen queue diverged from approved CAP evidence")
    original = json.loads(contract.workflow_path.read_text(encoding="utf-8"))
    if not isinstance(original, dict):
        raise GuidedEditExecutionError("Sealed Qwen workflow is not a graph")
    expected_graph = copy.deepcopy(original)
    loader = job.workflow.get("171")
    if not isinstance(loader, dict) or not isinstance(loader.get("inputs"), dict):
        raise GuidedEditExecutionError("Managed Qwen queue loader is missing")
    queue_file = loader["inputs"].get("queue_file")
    if not isinstance(queue_file, str):
        raise GuidedEditExecutionError("Managed Qwen queue file is missing")
    expected_graph["171"]["inputs"]["queue_file"] = queue_file
    expected_graph["171"]["inputs"]["job_index"] = 0
    expected_graph["171"]["inputs"]["quality_mode"] = "standard"
    expected_graph["170:169"]["inputs"]["seed"] = item["seed"]
    if job.workflow != expected_graph:
        raise GuidedEditExecutionError("Prepared Qwen API graph was altered after review")


def execute_prepared_managed_qwen_edit(
    contract: SpatialCorrectionContract,
    job: ManagedQwenCorrectionJob,
    *,
    operator_confirmed: bool,
    comfyui_url: str = "http://127.0.0.1:8188",
    timeout_seconds: float = 3600.0,
    client: XCICCoreClient | None = None,
) -> GuidedEditOutput:
    """Exactly one submission, never an automatic retry, no CAP DB access."""
    if operator_confirmed is not True:
        raise GuidedEditExecutionError("Explicit operator confirmation required")
    base = _loopback_endpoint(comfyui_url)
    if not 1 <= timeout_seconds <= 7200:
        raise GuidedEditExecutionError("Invalid ComfyUI edit timeout")
    if contract.mask_path is not None:
        raise GuidedEditExecutionError("Managed Qwen correction does not support masks")
    _unchanged(contract, job)
    queue_jobs = job.queue.get("jobs")
    if (
        not isinstance(queue_jobs, list)
        or len(queue_jobs) != 1
        or not isinstance(queue_jobs[0], dict)
        or not isinstance(queue_jobs[0].get("positive_prompt"), str)
        or not queue_jobs[0]["positive_prompt"].strip()
    ):
        raise GuidedEditExecutionError("Managed Qwen edit prompt is missing")
    provider = client if client is not None else XCICCoreClient(base)
    provider.healthcheck()
    provider.validate_nodes(job.workflow)
    validate_managed_qwen_model_choices(job.workflow, provider.object_info())
    _unchanged(contract, job)
    # The journal is written before queue construction and any network POST.
    reserve_guided_edit_attempt(contract)
    loader = job.workflow.get("171")
    if not isinstance(loader, dict) or not isinstance(loader.get("inputs"), dict):
        raise GuidedEditExecutionError("Managed loader is missing")
    queue_value = loader["inputs"].get("queue_file")
    if not isinstance(queue_value, str):
        raise GuidedEditExecutionError("Managed loader queue is missing")
    queue_path = Path(queue_value)
    output_path = job.output_path
    project = contract.project_root.resolve(strict=True)
    runtime = (project / ".vscs" / "runtime" / "comfyui").resolve(strict=False)
    if (
        queue_path.resolve(strict=False).parent != runtime / "queues"
        or output_path.resolve(strict=False).parent.parent.parent != runtime / "jobs"
    ):
        raise GuidedEditExecutionError("Managed edit runtime paths are not trusted")
    for directory in (queue_path.parent, output_path.parent):
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink() or not directory.is_dir():
            raise GuidedEditExecutionError("Managed edit runtime directory is unsafe")
    with queue_path.open("x", encoding="utf-8") as stream:
        json.dump(job.queue, stream, indent=2, sort_keys=True)
        stream.flush()
    _unchanged(contract, job)
    prompt_id = provider.submit(job.workflow)
    provider.wait(prompt_id, timeout_seconds=timeout_seconds)
    deadline = time.monotonic() + 15.0
    while not output_path.is_file() and time.monotonic() < deadline:
        time.sleep(0.25)
    if not output_path.is_file() or output_path.is_symlink():
        raise GuidedEditExecutionError("Expected edited PNG output is missing or unsafe")
    with output_path.open("rb") as stream:
        data = stream.read(_MAX_BYTES + 1)
    width, height = _checked_png(data, maximum_bytes=_MAX_BYTES)
    if width < 256 or height < 256:
        raise GuidedEditExecutionError("Edited PNG is smaller than CAP limits")
    _unchanged(contract, job)
    return GuidedEditOutput(
        content=data,
        image_sha256=hashlib.sha256(data).hexdigest(),
        width=width,
        height=height,
        prompt_id=prompt_id,
        output_node_id="9",
        filename=output_path.name,
        workflow_sha256=job.workflow_sha256,
        contract_sha256=contract.evidence_sha256,
        executed_prompt=str(job.queue["jobs"][0]["positive_prompt"]),
    )
