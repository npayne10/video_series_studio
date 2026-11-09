"""F4B: inspect the existing managed Qwen reference-edit graph without execution.

The managed derived-reference graph uses custom XCIC loader/output nodes,
not LoadImage/SaveImage. It is not a CAP correction authorization.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOADER = "171"
_SOURCE = "170:160"
_ENCODE = "170:156"
_POSITIVE = "170:151"
_NEGATIVE = "170:149"
_LORA = "170:153"
_MODEL = "170:161"
_SAMPLER = "170:169"
_DECODE = "170:158"
_OUTPUT = "9"


class ManagedQwenEditError(RuntimeError):
    """The managed Qwen editing graph does not match its reviewed contract."""


@dataclass(frozen=True, slots=True)
class ManagedQwenEditInspection:
    """Real graph topology evidence, never live execution authority."""

    workflow_sha256: str
    workflow_path: Path
    loader_node_id: str
    sampler_node_id: str
    output_node_id: str
    model_name: str
    lora_name: str
    blockers: tuple[str, ...]

    @property
    def execution_authorized(self) -> bool:
        return False


def _node(graph: dict[str, Any], key: str, kind: str) -> dict[str, Any]:
    item = graph.get(key)
    if not isinstance(item, dict) or item.get("class_type") != kind:
        raise ManagedQwenEditError(f"Managed workflow node {key} is not {kind}")
    inputs = item.get("inputs")
    if not isinstance(inputs, dict):
        raise ManagedQwenEditError(f"Managed workflow node {key} has invalid inputs")
    return inputs


def _edge(inputs: dict[str, Any], name: str, node_id: str, port: int) -> None:
    if inputs.get(name) != [node_id, port]:
        raise ManagedQwenEditError(f"Managed Qwen edit graph has changed: {name}")


def inspect_managed_qwen_edit_workflow(path: Path) -> ManagedQwenEditInspection:
    """Validate the checked-in reference-conditioning route, no I/O beyond JSON."""
    try:
        data = path.read_bytes()
        graph = json.loads(data)
    except (OSError, ValueError) as exc:
        raise ManagedQwenEditError("Managed Qwen workflow cannot be read") from exc
    if not isinstance(graph, dict) or not graph:
        raise ManagedQwenEditError("Managed Qwen workflow is not an API graph")
    loader = _node(graph, _LOADER, "XCICQwenReferenceJobLoader")
    if loader.get("queue_file") != "__VSCS_QUEUE_FILE__":
        raise ManagedQwenEditError("Managed loader queue placeholder has changed")
    source = _node(graph, _SOURCE, "FluxKontextImageScale")
    _edge(source, "image", _LOADER, 0)
    vae_latent = _node(graph, _ENCODE, "VAEEncode")
    _edge(vae_latent, "pixels", _SOURCE, 0)
    positive = _node(graph, _POSITIVE, "TextEncodeQwenImageEditPlus")
    negative = _node(graph, _NEGATIVE, "TextEncodeQwenImageEditPlus")
    for conditioning, port in ((positive, 1), (negative, 2)):
        _edge(conditioning, "prompt", _LOADER, port)
        _edge(conditioning, "image1", _SOURCE, 0)
    model = _node(graph, _MODEL, "UNETLoader")
    model_name = model.get("unet_name")
    if not isinstance(model_name, str) or not model_name.endswith(
        "qwen_image_edit_2511_fp8mixed.safetensors"
    ):
        raise ManagedQwenEditError("Managed Qwen edit checkpoint selection changed")
    lora = _node(graph, _LORA, "LoraLoaderModelOnly")
    lora_name = lora.get("lora_name")
    if not isinstance(lora_name, str) or "Qwen-Image-Edit-2511-Lightning-4steps" not in lora_name:
        raise ManagedQwenEditError("Managed Qwen edit LoRA selection changed")
    sampler = _node(graph, _SAMPLER, "KSampler")
    _edge(sampler, "latent_image", _ENCODE, 0)
    _edge(sampler, "positive", "170:148", 0)
    _edge(sampler, "negative", "170:147", 0)
    _node(graph, "170:148", "FluxKontextMultiReferenceLatentMethod")
    _node(graph, "170:147", "FluxKontextMultiReferenceLatentMethod")
    _edge(graph["170:148"]["inputs"], "conditioning", _POSITIVE, 0)
    _edge(graph["170:147"]["inputs"], "conditioning", _NEGATIVE, 0)
    decoded = _node(graph, _DECODE, "VAEDecode")
    _edge(decoded, "samples", _SAMPLER, 0)
    saved = _node(graph, _OUTPUT, "XCICSaveReferenceCandidate")
    _edge(saved, "images", _DECODE, 0)
    _edge(saved, "directory", _LOADER, 4)
    _edge(saved, "filename", _LOADER, 5)
    blockers = (
        "Existing provider requires a locked MASTER, not a supplementary Candidate",
        "CAP F3 source, mask and attempt journal are not wired to XCIC loader",
        "Custom output writer is not the SaveImage history transport",
        "Operator consent, runtime node inventory and 16 GiB GPU fit unverified",
    )
    return ManagedQwenEditInspection(
        workflow_sha256=hashlib.sha256(data).hexdigest(),
        workflow_path=path,
        loader_node_id=_LOADER,
        sampler_node_id=_SAMPLER,
        output_node_id=_OUTPUT,
        model_name=model_name,
        lora_name=lora_name,
        blockers=blockers,
    )
