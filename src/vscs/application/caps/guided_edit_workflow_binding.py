"""F4B: guarded Qwen editing input binding, with no live execution.

Graph node IDs and inputs must come from a reviewed ComfyUI API export.
This module stages immutable source/mask bytes, builds a working copy of
the workflow, and never calls POST /prompt or consumes an attempt.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from vscs.application.caps.spatial_correction_contract import (
    SpatialCorrectionContract,
    verify_spatial_contract,
)
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+\.png$")
_PNG = b"\x89PNG\r\n\x1a\n"


class GuidedEditBindingError(RuntimeError):
    """Refuse an unreviewed source/mask mapping or changed edit evidence."""


@dataclass(frozen=True, slots=True)
class GuidedEditNodeMap:
    """Reviewed, explicit input locations in the actual ComfyUI API workflow."""

    source_node_id: str
    source_input: str
    prompt_node_id: str
    prompt_input: str
    mask_node_id: str | None = None
    mask_input: str | None = None


@dataclass(frozen=True, slots=True)
class GuidedEditStagedInputs:
    """Files staged exclusively under the selected ComfyUI input root."""

    source_filename: str
    source_path: Path
    source_sha256: str
    mask_filename: str | None
    mask_path: Path | None
    mask_sha256: str | None

    def cleanup(self) -> None:
        """Remove only unmodified staging files; never touch source evidence."""
        for path, expected in (
            (self.source_path, self.source_sha256),
            (self.mask_path, self.mask_sha256),
        ):
            if path is not None and expected is not None and path.is_file():
                if _digest(path.read_bytes()) == expected:
                    path.unlink()


@dataclass(frozen=True, slots=True)
class GuidedEditBoundWorkflow:
    """Prepared offline workflow; NOT authorized for ComfyUI submission."""

    prompt: dict[str, Any]
    contract_sha256: str
    workflow_sha256: str
    source_filename: str
    mask_filename: str | None

    @property
    def execution_authorized(self) -> bool:
        return False


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _input_slot(
    graph: dict[str, Any],
    node_id: str,
    input_name: str,
    expected_types: frozenset[str],
) -> dict[str, Any]:
    node = graph.get(node_id)
    if not isinstance(node, dict) or node.get("class_type") not in expected_types:
        raise GuidedEditBindingError("Explicit editing node mapping is invalid")
    inputs = node.get("inputs")
    if not isinstance(inputs, dict) or input_name not in inputs:
        raise GuidedEditBindingError("Explicit editing input is missing from exported workflow")
    if not isinstance(inputs[input_name], str):
        raise GuidedEditBindingError("Editing input is not a literal string field")
    return inputs


def _validated_map(mapping: GuidedEditNodeMap, mask_present: bool) -> None:
    if bool(mapping.mask_node_id) != bool(mapping.mask_input):
        raise GuidedEditBindingError("Mask node ID and input must be supplied together")
    if mask_present != bool(mapping.mask_node_id):
        raise GuidedEditBindingError("Workflow mask mapping disagrees with governed mask")


def bind_guided_edit_workflow(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
    mapping: GuidedEditNodeMap,
    *,
    source_filename: str,
    mask_filename: str | None,
) -> GuidedEditBoundWorkflow:
    """Bind filenames and reviewed CAP prompt to a copied, reviewed API graph."""
    verify_spatial_contract(service, plan, contract)
    contract.verify_seal()
    _validated_map(mapping, contract.mask_path is not None)
    if not _SAFE_NAME.fullmatch(source_filename):
        raise GuidedEditBindingError("Source staging filename is unsafe")
    if mask_filename is not None and not _SAFE_NAME.fullmatch(mask_filename):
        raise GuidedEditBindingError("Mask staging filename is unsafe")
    if (mask_filename is None) != (contract.mask_path is None):
        raise GuidedEditBindingError("Mask staging does not match the contract")
    raw = contract.workflow_path.read_bytes()
    if _digest(raw) != contract.workflow_sha256:
        raise GuidedEditBindingError("Editing workflow changed after contract validation")
    graph = json.loads(raw)
    if not isinstance(graph, dict):
        raise GuidedEditBindingError("Editing workflow is not a JSON object")
    editable = copy.deepcopy(graph)
    source = _input_slot(
        editable, mapping.source_node_id, mapping.source_input,
        frozenset({"LoadImage"}),
    )
    positive = _input_slot(
        editable, mapping.prompt_node_id, mapping.prompt_input,
        frozenset({"TextEncodeQwenImageEdit", "TextEncodeQwenImageEditPlus"}),
    )
    if contract.mask_path is not None:
        assert mapping.mask_node_id is not None
        assert mapping.mask_input is not None
        mask = _input_slot(
            editable, mapping.mask_node_id, mapping.mask_input,
            frozenset({"LoadImageMask"}),
        )
        assert mask_filename is not None
        mask[mapping.mask_input] = mask_filename
    # Only the reviewed CAP rules are executable instructions. Semantic
    # evaluator free text is excluded. No direct edits to Canon/MASTER.
    prompt = "\n".join(f"{key}: {value}" for key, value in contract.accepted_fields)
    if not prompt.strip():
        raise GuidedEditBindingError("No accepted CAP constraints")
    source[mapping.source_input] = source_filename
    positive[mapping.prompt_input] = prompt
    return GuidedEditBoundWorkflow(
        prompt=editable,
        contract_sha256=contract.evidence_sha256,
        workflow_sha256=contract.workflow_sha256,
        source_filename=source_filename,
        mask_filename=mask_filename,
    )


def stage_guided_edit_inputs(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
    *,
    comfyui_input_directory: Path,
    trusted_comfyui_directory: Path,
) -> GuidedEditStagedInputs:
    """Copy governed PNG evidence into a unique non-overwriting input directory.

    This performs local file writes only, *not* generation, model loading,
    network access, Canon mutation or attempt consumption.
    """
    verify_spatial_contract(service, plan, contract)
    input_root = (trusted_comfyui_directory / "input").resolve(strict=True)
    if comfyui_input_directory.resolve(strict=True) != input_root:
        raise GuidedEditBindingError("Input directory differs from trusted ComfyUI input root")
    if not input_root.is_dir() or input_root.is_symlink():
        raise GuidedEditBindingError("ComfyUI input root must be a normal directory")
    source = contract.source_path.read_bytes()
    if not source.startswith(_PNG) or _digest(source) != contract.source_sha256:
        raise GuidedEditBindingError("Source image changed before staging")
    mask = None
    if contract.mask_path is not None:
        mask = contract.mask_path.read_bytes()
        if not mask.startswith(_PNG) or _digest(mask) != contract.mask_sha256:
            raise GuidedEditBindingError("Mask image changed before staging")
    token = uuid4().hex
    source_name = f"vscs_guided_{token}.png"
    mask_name = f"vscs_guided_{token}_mask.png" if mask is not None else None
    source_out = input_root / source_name
    mask_out = input_root / mask_name if mask_name is not None else None
    try:
        with source_out.open("xb") as stream:
            stream.write(source)
        if mask_out is not None and mask is not None:
            with mask_out.open("xb") as stream:
                stream.write(mask)
    except OSError:
        source_out.unlink(missing_ok=True)
        if mask_out is not None:
            mask_out.unlink(missing_ok=True)
        raise
    return GuidedEditStagedInputs(
        source_filename=source_name,
        source_path=source_out,
        source_sha256=contract.source_sha256,
        mask_filename=mask_name,
        mask_path=mask_out,
        mask_sha256=contract.mask_sha256,
    )
