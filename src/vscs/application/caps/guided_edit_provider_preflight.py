"""B.5.26F F4: fail-closed Qwen image-edit provider graph preflight.

No workflow execution, image uploads, side effects or corrections are
permitted here. A separate F4 live adapter requires a validated API export,
staging, capacity acceptance and explicit operator consent.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from vscs.application.caps.spatial_correction_contract import (
    SpatialCorrectionContract,
    SpatialCorrectionContractError,
    verify_spatial_contract,
)
from vscs.application.caps.visual_candidate_regeneration import (
    CandidateRegenerationPlan,
    CandidateRegenerationService,
)

_QWEN_EDIT = "qwen_image_edit_2511"
_EDIT_ENCODERS = ("textencodeqwenimageedit", "qwenimageedit", "qwen_image_edit")
_IMAGE_LOADERS = frozenset({"LoadImage", "LoadImageFromPath"})
_SAMPLERS = frozenset({"KSampler", "KSamplerAdvanced"})
_DECODE = frozenset({"VAEDecode"})
_OUTPUT = frozenset({"SaveImage", "XCICSaveImage"})
_LATENT_INPUT = frozenset({"EmptyLatentImage", "EmptySD3LatentImage"})


class GuidedEditPreflightError(RuntimeError):
    """A source-image-conditioned editing workflow cannot yet be trusted."""


@dataclass(frozen=True, slots=True)
class GuidedEditPreflight:
    """Review-only readiness evidence, never an operator execution grant."""

    contract_sha256: str
    graph_sha256: str
    source_loader_ids: tuple[str, ...]
    sampler_ids: tuple[str, ...]
    model_file: Path
    checkpoint_bytes: int
    blockers: tuple[str, ...]

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def graph_validated(self) -> bool:
        return not self.blockers


def _links(value: Any, nodes: dict[str, Any]) -> tuple[str, ...]:
    if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
        if value[0] in nodes and type(value[1]) is int:
            return (value[0],)
    return ()


def _upstream(graph: dict[str, Any], node_id: str) -> set[str]:
    seen: set[str] = set()
    pending = [node_id]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        node = graph[current]
        for value in node["inputs"].values():
            pending.extend(_links(value, graph))
    return seen


def _is_edit_model_file(checkpoint: Path, trusted_root: Path) -> Path:
    root = trusted_root.resolve(strict=True)
    path = checkpoint.resolve(strict=True)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise GuidedEditPreflightError("Checkpoint path escapes trusted ComfyUI models") from exc
    if checkpoint.is_symlink() or not path.is_file() or path.suffix.lower() != ".safetensors":
        raise GuidedEditPreflightError("Editing checkpoint must be an ordinary safetensors file")
    if _QWEN_EDIT not in path.name.lower():
        raise GuidedEditPreflightError("Selected checkpoint is not Qwen-Image-Edit-2511")
    return path


def inspect_guided_edit_graph(
    service: CandidateRegenerationService,
    plan: CandidateRegenerationPlan,
    contract: SpatialCorrectionContract,
    *,
    model_file: Path,
    trusted_model_directory: Path,
) -> GuidedEditPreflight:
    """Verify provenance, a graph source-to-sampler path and checkpoint presence.

    This never loads a model or calls ComfyUI. Any missing evidence is a blocker.
    The analysis cannot establish 16 GiB feasibility or compatible conditioning.
    """
    try:
        verify_spatial_contract(service, plan, contract)
    except SpatialCorrectionContractError as exc:
        raise GuidedEditPreflightError(str(exc)) from exc
    model = _is_edit_model_file(model_file, trusted_model_directory)
    try:
        graph = json.loads(contract.workflow_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GuidedEditPreflightError("Cannot parse edit graph") from exc
    if not isinstance(graph, dict) or not graph or not all(
        isinstance(node_id, str)
        and isinstance(node, dict)
        and isinstance(node.get("class_type"), str)
        and isinstance(node.get("inputs"), dict)
        for node_id, node in graph.items()
    ):
        raise GuidedEditPreflightError("Malformed editing API graph")
    typed: dict[str, list[str]] = {}
    for node_id, node in graph.items():
        typed.setdefault(node["class_type"], []).append(node_id)
    source_nodes = tuple(
        node_id for kind in _IMAGE_LOADERS for node_id in typed.get(kind, [])
    )
    samplers = tuple(
        node_id for kind in _SAMPLERS for node_id in typed.get(kind, [])
    )
    output_nodes = tuple(
        node_id for kind in _OUTPUT for node_id in typed.get(kind, [])
    )
    decoders = tuple(
        node_id for kind in _DECODE for node_id in typed.get(kind, [])
    )
    encoder_nodes = tuple(
        node_id
        for node_id, node in graph.items()
        if any(token in node["class_type"].lower() for token in _EDIT_ENCODERS)
    )
    blockers: list[str] = []
    if not source_nodes:
        blockers.append("No explicit LoadImage source node")
    if not samplers:
        blockers.append("No supported sampling node")
    if not encoder_nodes:
        blockers.append("No Qwen image-edit conditioning node")
    if not decoders or not output_nodes:
        blockers.append("No decode-to-output path")
    if any(node["class_type"] in _LATENT_INPUT for node in graph.values()):
        blockers.append("Fresh empty-latent node present; editing must use source conditioning")
    if source_nodes and samplers and not any(
        set(source_nodes) & _upstream(graph, sampler) for sampler in samplers
    ):
        blockers.append("Source image is not upstream of any sampler")
    if encoder_nodes and samplers and not any(
        set(encoder_nodes) & _upstream(graph, sampler) for sampler in samplers
    ):
        blockers.append("Qwen editing conditioning is not upstream of sampling")
    if decoders and output_nodes and not any(
        set(decoders) & _upstream(graph, output) for output in output_nodes
    ):
        blockers.append("No decoded image connected to an output node")
    if contract.mask_path is not None and not any(
        "mask" in node["class_type"].lower() or "inpaint" in node["class_type"].lower()
        for node in graph.values()
    ):
        blockers.append("Supplied mask has no mask/inpainting node")
    if contract.model_identifier.lower() not in model.name.lower():
        blockers.append("Contract model identifier and checkpoint do not match")
    referenced_models = [
        value
        for node in graph.values()
        for key, value in node["inputs"].items()
        if key in {"unet_name", "model_name", "ckpt_name"}
        and isinstance(value, str)
    ]
    if model.name not in {
        PureWindowsPath(name).name for name in referenced_models
    }:
        blockers.append("Qwen edit checkpoint is not selected in workflow graph")
    # Even with a linked graph, dynamic source binding and ComfyUI execution
    # are unavailable until an explicit operator-approved provider is implemented.
    blockers.append(
        "No validated per-request image staging, live VRAM test or operator execution consent"
    )
    return GuidedEditPreflight(
        contract_sha256=contract.evidence_sha256,
        graph_sha256=hashlib.sha256(contract.workflow_path.read_bytes()).hexdigest(),
        source_loader_ids=source_nodes,
        sampler_ids=samplers,
        model_file=model,
        checkpoint_bytes=model.stat().st_size,
        blockers=tuple(blockers),
    )
