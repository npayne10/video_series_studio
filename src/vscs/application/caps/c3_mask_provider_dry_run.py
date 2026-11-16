"""F5.4.2 C3: read-only provider mask compatibility and offline dry-run.

C3 never submits a ComfyUI prompt, stages input, reserves an attempt or
authorizes generation. An HTTP probe, when requested, uses loopback GET only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vscs.application.caps.geometry_correction_policy import GeometryCorrectionError
from vscs.application.caps.governed_visual_correction_handoff import (
    GovernedCorrectionProposal,
)
from vscs.application.caps.guided_edit_capability_assessment import (
    _get_json,
    _loopback_base,
)
from vscs.application.caps.human_reviewed_mask_evidence import prepare_reviewed_mask
from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.persistent_human_review import (
    list_existing_mask_versions,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.application.caps.qwen_mask_aware_qualification import (
    build_experimental_masked_graph,
    validate_experimental_graph,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualitySnapshot

_REQUIRED_MASK_NODES = frozenset(
    {"LoadImageMask", "SetLatentNoiseMask", "ImageCompositeMasked"}
)
_EXPECTED_MASK_INPUTS = {
    "LoadImageMask": frozenset({"image", "channel"}),
    "SetLatentNoiseMask": frozenset({"samples", "mask"}),
    "ImageCompositeMasked": frozenset(
        {"destination", "source", "mask", "x", "y", "resize_source"}
    ),
}


@dataclass(frozen=True, slots=True)
class C3MaskDryRun:
    source_sha256: str
    proposal_sha256: str
    selected_mask_sha256: str | None
    managed_workflow_sha256: str | None
    experimental_graph_sha256: str | None
    selected_mask_current: bool
    graph_topology_inspected: bool
    endpoint_probed: bool
    remote_nodes_reported: tuple[str, ...]
    gpu_devices: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def mask_provider_compatibility_verified(self) -> bool:
        # Static node schemas alone cannot prove runtime mask behavior.
        return False

    @property
    def protected_pixels_verified(self) -> bool:
        return False

    @property
    def governed_attempt_allowed(self) -> bool:
        return False

    @property
    def candidate_registration_allowed(self) -> bool:
        return False

    def describe(self) -> str:
        return "\n".join(
            (
                "F5.4.2 STAGE C3 — PROVIDER MASK COMPATIBILITY DRY-RUN",
                "READ ONLY / NO GENERATION / NO WRITES",
                f"Candidate source SHA-256: {self.source_sha256}",
                f"C1 proposal SHA-256: {self.proposal_sha256}",
                f"Selected mask SHA-256: {self.selected_mask_sha256 or 'none'}",
                f"Mask matches current proposal: {self.selected_mask_current}",
                f"Managed Qwen workflow SHA-256: {self.managed_workflow_sha256 or 'unavailable'}",
                f"Derived experimental graph SHA-256: {self.experimental_graph_sha256 or 'unavailable'}",
                f"Offline topology inspected: {self.graph_topology_inspected}",
                f"Loopback GET probe used: {self.endpoint_probed}",
                "Available mask nodes: " + (", ".join(self.remote_nodes_reported) or "not checked"),
                "Reported GPU: " + ("; ".join(self.gpu_devices) or "not checked"),
                "C3 IS NOT AN EXECUTION CONSENT. C4 is a separate gate.",
                "No POST /prompt, no ComfyUI staging, no GPU inference, no paid API,",
                "no attempt reservation, image write, Candidate registration or CAP/Canon promotion.",
                "Blockers / unresolved verification:",
                *(f"- {blocker}" for blocker in self.blockers),
            )
        )


def _inventory(
    url: str, timeout: float
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = _loopback_base(url)
    if not 0 < timeout <= 10:
        raise GeometryCorrectionError("C3 GET timeout must be 0–10 seconds")
    return (
        _get_json(base, "/object_info", timeout),
        _get_json(base, "/system_stats", timeout),
    )


def inspect_c3_mask_dry_run(
    snapshot: CandidateQualitySnapshot,
    proposal: GovernedCorrectionProposal,
    *,
    selected_mask_path: Path | None,
    workflow_path: Path | None = None,
    probe_local_comfyui: bool = False,
    comfyui_url: str = "http://127.0.0.1:8188",
    timeout: float = 3.0,
) -> C3MaskDryRun:
    """Inspect saved mask provenance and Qwen topology; optionally GET ComfyUI.

    The experimental graph is a temporary in-memory derivation only.
    No network call occurs unless probe_local_comfyui=True.
    """
    proposal.verify_seal()
    if (
        proposal.asset_id != snapshot.asset_id
        or proposal.source_reference_id != snapshot.reference_id
        or proposal.source_sha256 != snapshot.image_sha256
    ):
        raise GeometryCorrectionError("C3 source and C1 proposal are not bound")
    # Current source SHA, exact canonical mask path and stored bytes validated
    # by existing C2.1 list; this operation never changes either artifact.
    versions = list_existing_mask_versions(snapshot, proposal=proposal)
    blockers: list[str] = []
    selected = next(
        (v for v in versions if v.path == selected_mask_path),
        None,
    )
    if selected_mask_path is None:
        blockers.append("No existing C2 mask was explicitly selected")
    elif selected is None:
        blockers.append("Selected C2 mask is missing, unsafe or not present in C2.1 inventory")
    elif not selected.matches_current_proposal:
        blockers.append("Selected mask is HISTORICAL; it is not bound to current C1 ROI")
    # Only derive the expected byte digest; never create or save a new C2 mask.
    expected = prepare_reviewed_mask(
        proposal,
        source_path=snapshot.image_path,
        reviewer_confirmed_mask=True,
    )
    if selected is not None and selected.matches_current_proposal:
        if selected.sha256 != expected.mask_sha256:
            blockers.append("Current mask SHA does not match reviewed proposal")
    managed_sha: str | None = None
    experimental_sha: str | None = None
    topology_inspected = False
    workflow = workflow_path if workflow_path is not None else default_workflow_path()
    try:
        managed = inspect_managed_qwen_edit_workflow(workflow)
        managed_sha = managed.workflow_sha256
        derived = build_experimental_masked_graph(workflow_path=workflow)
        validate_experimental_graph(derived)
        # Known isolated F5.4.1B topology has a mask-to-latent path and
        # post-decode compositing, but it is NOT a validated CAP provider.
        if not all(
            any(node.get("class_type") == kind for node in derived.values())
            for kind in _REQUIRED_MASK_NODES
        ):
            blockers.append("Derived graph lacks mandatory mask topology")
        else:
            import json

            experimental_sha = hashlib.sha256(
                json.dumps(derived, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            topology_inspected = True
    except (OSError, ValueError, RuntimeError) as exc:
        blockers.append(f"Qwen graph inspection blocked: {type(exc).__name__}")
    blockers.extend(
        (
            "Managed Qwen XCIC graph does not accept a C2 mask or a supplementary Candidate directly",
            "F5.4.1B derived graph remains experimental; input filenames are unbound",
            "Mask polarity, latent-mask behavior and protected-pixel compositing unverified by live output",
            "RTX 5060 Ti 16 GiB peak VRAM and successful inference are unverified",
            "C4 consent, attempt accounting, Candidate output and registration contracts are absent",
        )
    )
    nodes: tuple[str, ...] = ()
    devices: tuple[str, ...] = ()
    if probe_local_comfyui:
        try:
            info, stats = _inventory(comfyui_url, timeout)
            nodes = tuple(sorted(_REQUIRED_MASK_NODES.intersection(info)))
            missing = _REQUIRED_MASK_NODES - set(nodes)
            if missing:
                blockers.append(
                    "Local ComfyUI lacks required mask nodes: " + ", ".join(sorted(missing))
                )
            for kind, expected_inputs in _EXPECTED_MASK_INPUTS.items():
                descriptor = info.get(kind)
                if not isinstance(descriptor, dict):
                    continue
                groups = descriptor.get("input", {})
                required = groups.get("required", {}) if isinstance(groups, dict) else {}
                optional = groups.get("optional", {}) if isinstance(groups, dict) else {}
                if not isinstance(required, dict) or not isinstance(optional, dict):
                    blockers.append(f"Node schema {kind} is malformed")
                elif not expected_inputs.issubset(set(required) | set(optional)):
                    blockers.append(f"Node schema {kind} lacks expected input names")
            data = stats.get("devices")
            if isinstance(data, list):
                devices = tuple(
                    f"{item.get('name', 'GPU unknown')} "
                    f"({item['vram_total'] / (1024**3):.1f} GiB total)"
                    for item in data
                    if isinstance(item, dict)
                    and type(item.get("vram_total")) in (int, float)
                    and item["vram_total"] > 0
                )
            if not devices:
                blockers.append("No device/VRAM report received from ComfyUI")
        except (OSError, ValueError, RuntimeError) as exc:
            blockers.append(f"Local GET capability probe unavailable: {type(exc).__name__}")
    else:
        blockers.append("Live ComfyUI node schemas not checked (optional GET-only probe)")
    return C3MaskDryRun(
        source_sha256=snapshot.image_sha256,
        proposal_sha256=proposal.proposal_sha256,
        selected_mask_sha256=selected.sha256 if selected is not None else None,
        managed_workflow_sha256=managed_sha,
        experimental_graph_sha256=experimental_sha,
        selected_mask_current=bool(selected and selected.matches_current_proposal),
        graph_topology_inspected=topology_inspected,
        endpoint_probed=probe_local_comfyui,
        remote_nodes_reported=nodes,
        gpu_devices=devices,
        blockers=tuple(blockers),
    )
