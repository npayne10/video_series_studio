"""F5.4.2 C4B: isolated Qwen masked-provider API *qualification blueprint*.

No transport, prompt submission, staging, model loading, GPU inference,
governed attempt reservation or Candidate registration exists here.
Only an explicitly current source-bound C2 mask may produce a blueprint.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.caps.c4_mask_provider_contract import prepare_c4_provider_contract
from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
)
from vscs.application.caps.managed_qwen_correction_job import managed_qwen_positive_prompt
from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot

_SOURCE = "C4B_SOURCE"
_MASK = "C4B_MASK"
_SOURCE_SIZE = "C4B_SOURCE_SIZE"
_EDIT_SIZE = "C4B_EDIT_SIZE"
_MASK_IMAGE = "C4B_MASK_IMAGE"
_MASK_SCALE = "C4B_MASK_SCALE"
_EDIT_MASK = "C4B_EDIT_MASK"
_LATENT_MASK = "C4B_LATENT_MASK"
_RESULT_SCALE = "C4B_RESULT_SCALE"
_COMPOSITE = "C4B_COMPOSITE"
_OUTPUT_PREFIX = "C4B_DISPOSABLE_QUALIFICATION"
_SEED_MAX = (1 << 64) - 1

_REQUIRED_INPUTS: dict[str, frozenset[str]] = {
    "LoadImage": frozenset({"image"}),
    "LoadImageMask": frozenset({"image", "channel"}),
    "GetImageSize": frozenset({"image"}),
    "MaskToImage": frozenset({"mask"}),
    "ImageScale": frozenset({"image", "upscale_method", "width", "height", "crop"}),
    "ImageToMask": frozenset({"image", "channel"}),
    "SetLatentNoiseMask": frozenset({"samples", "mask"}),
    "ImageCompositeMasked": frozenset(
        {"destination", "source", "mask", "x", "y", "resize_source"}
    ),
    "SaveImage": frozenset({"images", "filename_prefix"}),
}


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class C4BProviderBlueprint:
    """In-memory evidence; graph is untrusted until reverified at every use."""

    graph: dict[str, Any]
    graph_sha256: str
    managed_template_sha256: str
    source_sha256: str
    mask_sha256: str
    c1_proposal_sha256: str
    source_input_filename: str
    mask_input_filename: str
    seed: int
    output_prefix: str
    binding_contract_verified_offline: bool
    node_schema_verified_live: bool = False
    runtime_mask_polarity_verified: bool = False
    runtime_vram_verified: bool = False
    protected_pixel_fidelity_verified: bool = False

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def input_staging_authorized(self) -> bool:
        return False

    @property
    def governed_attempt_allowed(self) -> bool:
        return False

    @property
    def candidate_registration_allowed(self) -> bool:
        return False

    def verify_seal(self) -> None:
        if _digest(self.graph) != self.graph_sha256:
            raise GeometryCorrectionError("C4B graph changed since offline qualification")
        validate_c4b_api_graph(self.graph)

    def describe(self) -> str:
        self.verify_seal()
        return "\n".join(
            (
                "F5.4.2 C4B - ISOLATED MASK PROVIDER BLUEPRINT (NO GENERATION)",
                f"Source SHA-256: {self.source_sha256}",
                f"C1 proposal SHA-256: {self.c1_proposal_sha256}",
                f"Current C2 mask SHA-256: {self.mask_sha256}",
                f"Managed Qwen baseline SHA-256: {self.managed_template_sha256}",
                f"Isolated API graph SHA-256: {self.graph_sha256}",
                f"Prepared source input name: {self.source_input_filename}",
                f"Prepared mask input name: {self.mask_input_filename}",
                f"Deterministic seed: {self.seed}",
                f"Output prefix (requires dedicated isolated ComfyUI output root): {self.output_prefix}",
                "Two mask paths: processed-size latent conditioning + original-size final composite.",
                "Original source is the final composite destination; protected pixels remain unedited in the planned graph.",
                "Node schema, mask polarity, GPU fit and live pixel fidelity: NOT VERIFIED.",
                "Input files have NOT been staged; SaveImage is NOT authorized on a shared server.",
                "No queue POST, GPU inference, payment, attempt reservation, registration or CAP promotion.",
                "This is a blueprint, NOT a qualified executable provider.",
            )
        )


def _node(kind: str, **inputs: Any) -> dict[str, Any]:
    return {"class_type": kind, "inputs": inputs}


def _build_isolated_graph(
    workflow_path: Path,
    *,
    source_name: str,
    mask_name: str,
    seed: int,
    positive: str,
) -> dict[str, Any]:
    """Derive a new core-IO graph from the inspected Qwen model route."""
    inspect_managed_qwen_edit_workflow(workflow_path)
    graph: dict[str, Any] = copy.deepcopy(
        json.loads(workflow_path.read_text(encoding="utf-8"))
    )
    # Remove every XCIC queue/output dependency and LoRA/switch path;
    # qualification will use fixed 20-step, non-LoRA baseline.
    for key in ("171", "170:153", "170:154", "170:155", "170:163",
                "170:164", "170:165", "170:166", "170:167", "170:168"):
        graph.pop(key)
    graph["170:160"]["inputs"]["image"] = [_SOURCE, 0]
    graph["170:151"]["inputs"]["prompt"] = positive
    graph["170:149"]["inputs"]["prompt"] = "Unrequested changes to the scene or objects."
    sampler = graph["170:169"]["inputs"]
    sampler["seed"] = seed
    sampler["steps"] = 20
    sampler["cfg"] = 1.0
    sampler["model"] = ["170:152", 0]
    sampler["latent_image"] = [_LATENT_MASK, 0]

    # Mask must be resized to the processed image for latent conditioning;
    # the original mask is separately used for final original-size composite.
    graph[_SOURCE] = _node("LoadImage", image=source_name)
    graph[_MASK] = _node("LoadImageMask", image=mask_name, channel="red")
    graph[_SOURCE_SIZE] = _node("GetImageSize", image=[_SOURCE, 0])
    graph[_EDIT_SIZE] = _node("GetImageSize", image=["170:160", 0])
    graph[_MASK_IMAGE] = _node("MaskToImage", mask=[_MASK, 0])
    graph[_MASK_SCALE] = _node(
        "ImageScale",
        image=[_MASK_IMAGE, 0],
        upscale_method="nearest-exact",
        width=[_EDIT_SIZE, 0],
        height=[_EDIT_SIZE, 1],
        crop="center",
    )
    graph[_EDIT_MASK] = _node("ImageToMask", image=[_MASK_SCALE, 0], channel="red")
    graph[_LATENT_MASK] = _node(
        "SetLatentNoiseMask", samples=["170:156", 0], mask=[_EDIT_MASK, 0]
    )
    graph[_RESULT_SCALE] = _node(
        "ImageScale",
        image=["170:158", 0],
        upscale_method="lanczos",
        width=[_SOURCE_SIZE, 0],
        height=[_SOURCE_SIZE, 1],
        crop="center",
    )
    graph[_COMPOSITE] = _node(
        "ImageCompositeMasked",
        destination=[_SOURCE, 0],
        source=[_RESULT_SCALE, 0],
        mask=[_MASK, 0],
        x=0,
        y=0,
        resize_source=False,
    )
    # SaveImage will write to the ComfyUI instance's configured output root.
    # Never submit this graph to a shared/production server.
    graph["9"] = _node(
        "SaveImage", images=[_COMPOSITE, 0], filename_prefix=_OUTPUT_PREFIX
    )
    return graph


def validate_c4b_api_graph(graph: dict[str, Any]) -> None:
    """Fail closed on XCIC access, missing wiring, unreviewed node types."""
    if any(
        not isinstance(node, dict)
        or not isinstance(node.get("class_type"), str)
        or node["class_type"].startswith("XCIC")
        for node in graph.values()
    ):
        raise GeometryCorrectionError("C4B graph includes invalid or XCIC provider nodes")
    if "171" in graph:
        raise GeometryCorrectionError("C4B graph must not reference a managed XCIC queue")
    expected: dict[str, tuple[str, dict[str, Any]]] = {
        _SOURCE: ("LoadImage", {}),
        _MASK: ("LoadImageMask", {"channel": "red"}),
        _MASK_IMAGE: ("MaskToImage", {"mask": [_MASK, 0]}),
        _SOURCE_SIZE: ("GetImageSize", {"image": [_SOURCE, 0]}),
        _EDIT_SIZE: ("GetImageSize", {"image": ["170:160", 0]}),
        _MASK_SCALE: (
            "ImageScale",
            {"image": [_MASK_IMAGE, 0], "upscale_method": "nearest-exact",
             "width": [_EDIT_SIZE, 0], "height": [_EDIT_SIZE, 1], "crop": "center"},
        ),
        _EDIT_MASK: ("ImageToMask", {"image": [_MASK_SCALE, 0], "channel": "red"}),
        _LATENT_MASK: (
            "SetLatentNoiseMask",
            {"samples": ["170:156", 0], "mask": [_EDIT_MASK, 0]},
        ),
        _RESULT_SCALE: (
            "ImageScale",
            {"image": ["170:158", 0], "upscale_method": "lanczos",
             "width": [_SOURCE_SIZE, 0], "height": [_SOURCE_SIZE, 1], "crop": "center"},
        ),
        _COMPOSITE: (
            "ImageCompositeMasked",
            {"destination": [_SOURCE, 0], "source": [_RESULT_SCALE, 0],
             "mask": [_MASK, 0], "x": 0, "y": 0, "resize_source": False},
        ),
        "9": (
            "SaveImage",
            {"images": [_COMPOSITE, 0], "filename_prefix": _OUTPUT_PREFIX},
        ),
    }
    for key, (kind, required) in expected.items():
        node = graph.get(key)
        if not isinstance(node, dict) or node.get("class_type") != kind:
            raise GeometryCorrectionError(f"C4B graph node {key} is not {kind}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict) or any(inputs.get(k) != v for k, v in required.items()):
            raise GeometryCorrectionError(f"C4B masked graph wiring changed at {key}")
    source_inputs = graph[_SOURCE]["inputs"]
    mask_inputs = graph[_MASK]["inputs"]
    for name in (source_inputs.get("image"), mask_inputs.get("image")):
        if (
            not isinstance(name, str)
            or "/" in name
            or "\\" in name
            or not name.endswith(".png")
            or not name.startswith("c4b_")
        ):
            raise GeometryCorrectionError("C4B input filename must be an isolated PNG basename")
    sampler = graph.get("170:169", {}).get("inputs", {})
    if (
        sampler.get("latent_image") != [_LATENT_MASK, 0]
        or sampler.get("model") != ["170:152", 0]
        or sampler.get("steps") != 20
        or sampler.get("cfg") != 1.0
        or type(sampler.get("seed")) is not int
        or not 0 <= sampler["seed"] <= _SEED_MAX
    ):
        raise GeometryCorrectionError("C4B sampler must retain the fixed non-LoRA baseline")
    source = graph.get("170:160", {}).get("inputs", {})
    if source.get("image") != [_SOURCE, 0]:
        raise GeometryCorrectionError("C4B source scaling was disconnected")
    for node_id in ("170:151", "170:149"):
        value = graph.get(node_id, {}).get("inputs", {}).get("prompt")
        if not isinstance(value, str) or not value.strip():
            raise GeometryCorrectionError("C4B prompt must be source-bound and non-empty")
    for node in graph.values():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise GeometryCorrectionError("C4B graph contains malformed inputs")
        for value in inputs.values():
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and type(value[1]) is int
                and value[0] not in graph
            ):
                raise GeometryCorrectionError("C4B graph contains a dangling node reference")
    # The exact graph must equal a fresh derivation of the reviewed default
    # Qwen baseline; do not permit custom nodes, modified prompts or
    # alternate output sinks in a qualification blueprint.
    gold = _build_isolated_graph(
        default_workflow_path(),
        source_name=source_inputs["image"],
        mask_name=mask_inputs["image"],
        seed=sampler["seed"],
        positive=graph["170:151"]["inputs"]["prompt"],
    )
    if graph != gold:
        raise GeometryCorrectionError("C4B graph differs from the reviewed isolated baseline")


def inspect_c4b_node_schemas(
    graph: dict[str, Any], object_info: dict[str, Any]
) -> tuple[str, ...]:
    """Pure inspection of ComfyUI GET /object_info: no runtime inference."""
    validate_c4b_api_graph(graph)
    blockers: list[str] = []
    kinds = sorted({node["class_type"] for node in graph.values()})
    for kind in kinds:
        node = object_info.get(kind)
        if not isinstance(node, dict):
            blockers.append(f"ComfyUI lacks node class {kind}")
            continue
        declared = node.get("input", {})
        if not isinstance(declared, dict):
            blockers.append(f"Invalid node input schema for {kind}")
            continue
        required = declared.get("required", {})
        optional = declared.get("optional", {})
        if not isinstance(required, dict) or not isinstance(optional, dict):
            blockers.append(f"Invalid declared inputs for {kind}")
            continue
        available = set(required) | set(optional)
        expected = _REQUIRED_INPUTS.get(kind)
        if expected is not None and not expected.issubset(available):
            blockers.append(f"ComfyUI {kind} missing input names {sorted(expected - available)}")
        for node_data in graph.values():
            if node_data["class_type"] == kind:
                missing = set(node_data["inputs"]) - available
                if missing:
                    blockers.append(f"ComfyUI {kind} lacks graph inputs {sorted(missing)}")
    # Node-name/input-schema presence cannot establish output types,
    # mask polarity or any inference result.
    return tuple(blockers)


def prepare_c4b_isolated_blueprint(
    snapshot: CandidateQualitySnapshot,
    proposal: GovernedCorrectionProposal,
    *,
    selected_mask_path: Path,
    seed: int = 1729,
    workflow_path: Path | None = None,
) -> C4BProviderBlueprint:
    """Create a mask-aware, standalone API graph in memory; never run it."""
    if type(seed) is not int or not 0 <= seed <= _SEED_MAX:
        raise GeometryCorrectionError("C4B seed must be a fixed unsigned 64-bit integer")
    preparation = prepare_c4_provider_contract(
        snapshot, proposal, selected_mask_path=selected_mask_path, workflow_path=workflow_path
    )
    if not preparation.mask_matches_current_proposal:
        raise GeometryCorrectionError("C4B rejects HISTORICAL or non-current C2 mask")
    if not preparation.mask_node_wiring_validated_offline:
        raise GeometryCorrectionError("C4B requires the accepted C4A graph baseline")
    if not preparation.selected_mask_sha256:
        raise GeometryCorrectionError("C4B mask SHA-256 was not verified")
    source_name = f"c4b_source_{snapshot.image_sha256[:16]}.png"
    mask_name = f"c4b_mask_{preparation.selected_mask_sha256[:16]}.png"
    workflow = workflow_path if workflow_path is not None else default_workflow_path()
    graph = _build_isolated_graph(
        workflow,
        source_name=source_name,
        mask_name=mask_name,
        seed=seed,
        positive=managed_qwen_positive_prompt(proposal.accepted_fields, proposal.target_field),
    )
    validate_c4b_api_graph(graph)
    return C4BProviderBlueprint(
        graph=graph,
        graph_sha256=_digest(graph),
        managed_template_sha256=preparation.managed_workflow_sha256 or "",
        source_sha256=snapshot.image_sha256,
        mask_sha256=preparation.selected_mask_sha256,
        c1_proposal_sha256=proposal.proposal_sha256,
        source_input_filename=source_name,
        mask_input_filename=mask_name,
        seed=seed,
        output_prefix=_OUTPUT_PREFIX,
        binding_contract_verified_offline=True,
    )
