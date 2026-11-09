"""Build a governed CAP correction job for the existing XCIC Qwen edit loader.

Pure preparation: no queue write, ComfyUI POST, GPU load or attempt reservation.
The reference-conditioning queue format follows the working derived provider,
but takes its authority from the F3 supplementary Candidate contract instead
of a locked MASTER.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.caps.managed_qwen_edit_inspection import (
    ManagedQwenEditInspection,
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.spatial_correction_contract import (
    SpatialCorrectionContract,
    verify_spatial_contract,
)
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


class ManagedQwenCorrectionError(RuntimeError):
    """A CAP correction cannot safely use the managed image-edit workflow."""


@dataclass(frozen=True, slots=True)
class ManagedQwenCorrectionJob:
    """Bound queue and workflow in memory only; explicitly non-executable."""

    workflow: dict[str, Any]
    queue: dict[str, Any]
    contract_sha256: str
    workflow_sha256: str
    source_sha256: str
    output_path: Path

    @property
    def execution_authorized(self) -> bool:
        return False


def prepare_managed_qwen_correction(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
    *,
    workflow_path: Path,
    queue_path: Path,
    output_path: Path,
    job_id: str,
) -> ManagedQwenCorrectionJob:
    """Create a bounded one-image job from governed CAP image and constraints."""
    verify_spatial_contract(service, plan, contract)
    inspection: ManagedQwenEditInspection = inspect_managed_qwen_edit_workflow(workflow_path)
    if (
        workflow_path.resolve(strict=True) != contract.workflow_path.resolve(strict=True)
        or inspection.workflow_sha256 != contract.workflow_sha256
    ):
        raise ManagedQwenCorrectionError("Managed workflow differs from governed F3 evidence")
    if contract.mask_path is not None:
        raise ManagedQwenCorrectionError(
            "This managed Qwen graph has no validated mask input; masked corrections blocked"
        )
    if not _SAFE_ID.fullmatch(job_id) or plan.attempt != contract.correction_attempt:
        raise ManagedQwenCorrectionError("Job identity or attempt lineage is invalid")
    project = contract.project_root.resolve(strict=True)
    runtime = (project / ".vscs" / "runtime" / "comfyui").resolve(strict=False)
    expected_queues = runtime / "queues"
    expected_outputs = runtime / "jobs" / job_id / "output"
    if (
        queue_path.resolve(strict=False).parent != expected_queues
        or queue_path.name != f"cap_correction_{job_id}.json"
        or output_path.resolve(strict=False).parent != expected_outputs
        or output_path.name != f"cap_correction_{job_id}.png"
    ):
        raise ManagedQwenCorrectionError("Correction queue or output path is not isolated")
    if output_path.exists() or queue_path.exists():
        raise ManagedQwenCorrectionError("Correction output or queue already exists")
    if not plan.source.accepted_fields:
        raise ManagedQwenCorrectionError("No accepted CAP constraints are available")
    if contract.source_sha256 != plan.source.image_sha256:
        raise ManagedQwenCorrectionError("Source Candidate identity mismatch")
    raw = contract.workflow_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != inspection.workflow_sha256:
        raise ManagedQwenCorrectionError("Managed workflow changed during preparation")
    graph = json.loads(raw)
    if not isinstance(graph, dict):
        raise ManagedQwenCorrectionError("Managed workflow is not an API graph")
    editable: dict[str, Any] = copy.deepcopy(graph)
    loader = editable[inspection.loader_node_id]["inputs"]
    loader["queue_file"] = str(queue_path)
    loader["job_index"] = 0
    loader["quality_mode"] = "standard"
    editable[inspection.sampler_node_id]["inputs"]["seed"] = plan.request.seed
    positive = "\n".join(f"MANDATORY reviewed {key}: {value}" for key, value in contract.accepted_fields)
    category = plan.source.asset_id.upper().split("-")
    kinds = {
        "CHR": "character",
        "SHP": "ship",
        "PLN": "planet",
        "LOC": "location",
        "ENV": "environment",
        "UNI": "uniform",
        "PRP": "prop",
        "TEC": "technology",
        "VEH": "vehicle",
        "EFF": "effect",
    }
    queue_job = {
        "job_id": job_id,
        "asset_id": contract.asset_id,
        "asset_category": kinds.get(category[1] if len(category) > 1 else "", "asset"),
        "reference_inputs": [str(contract.source_path)],
        "positive_prompt": positive,
        "negative_prompt": plan.request.negative_prompt,
        "generation": {"enable_turbo_mode": True},
        "generation_policy": {"force_standard_mode": True},
        "output": {
            "candidate_directory": str(expected_outputs),
            "candidate_filename": output_path.name,
        },
        "seed": plan.request.seed,
    }
    return ManagedQwenCorrectionJob(
        workflow=editable,
        queue={"jobs": [queue_job]},
        contract_sha256=contract.evidence_sha256,
        workflow_sha256=inspection.workflow_sha256,
        source_sha256=contract.source_sha256,
        output_path=output_path,
    )
