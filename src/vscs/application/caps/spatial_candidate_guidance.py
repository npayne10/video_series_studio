"""B.5.26F read-only inspection of XCIC spatial-edit workflow readiness.

Node presence is not evidence of a connected guided-edit path. This module
never submits a provider job, modifies workflow files, or spends an attempt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vscs.infrastructure.xcic.config import XCICConfiguration

_IMAGE_INPUTS = frozenset({"image", "images", "pixels", "source_image"})
_MASK_INPUTS = frozenset({"mask", "noise_mask"})
_CONTROL_TOKENS = ("controlnet", "depth", "canny", "lineart", "pose", "segmentation")
_EDIT_TOKENS = ("inpaint", "imageedit", "image_edit", "reference", "ipadapter")


@dataclass(frozen=True, slots=True)
class SpatialGuidanceInspection:
    workflow_path: Path
    workflow_available: bool
    loader_count: int
    image_nodes: tuple[str, ...]
    mask_nodes: tuple[str, ...]
    control_nodes: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def guided_execution_verified(self) -> bool:
        """Never infer an executable spatial editor from node-name heuristics."""
        return False

    def describe(self) -> str:
        details = [
            "B.5.26F — Read-only XCIC spatial guidance inspection",
            f"Workflow: {self.workflow_path}",
            f"Workflow readable: {self.workflow_available}",
            f"XCIC queue loaders: {self.loader_count}",
            "Source-image/edit nodes: " + (", ".join(self.image_nodes) or "none detected"),
            "Mask/inpainting nodes: " + (", ".join(self.mask_nodes) or "none detected"),
            "Spatial control nodes: " + (", ".join(self.control_nodes) or "none detected"),
            "Guided execution verified: NO",
            "No ComfyUI request, GPU job, API charge or correction attempt was made.",
            "Blockers:",
            *(f"- {item}" for item in self.blockers),
        ]
        return "\n".join(details)


def inspect_spatial_guidance(config: XCICConfiguration) -> SpatialGuidanceInspection:
    """Inspect a configured local API workflow only; never contact ComfyUI."""
    path = config.text_workflow_path.expanduser().resolve(strict=False)
    blockers: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        blockers.append(f"Cannot read local XCIC workflow: {type(exc).__name__}: {exc}")
        raw = None
    if isinstance(raw, dict) and "nodes" in raw:
        blockers.append("Workflow is UI format; export an API-format workflow for inspection.")
        raw = None
    elif raw is not None and not isinstance(raw, dict):
        blockers.append("XCIC workflow must contain an API-format JSON object.")
        raw = None

    classes: list[str] = []
    image: list[str] = []
    mask: list[str] = []
    control: list[str] = []
    if isinstance(raw, dict):
        for node in raw.values():
            if not isinstance(node, dict):
                blockers.append("Malformed API workflow node.")
                continue
            kind = node.get("class_type")
            inputs = node.get("inputs")
            if not isinstance(kind, str) or not isinstance(inputs, dict):
                blockers.append("Malformed API workflow node type or inputs.")
                continue
            classes.append(kind)
            lower = kind.lower()
            names = {str(key).lower() for key in inputs}
            if "loadimage" in lower or "imageedit" in lower or "image_edit" in lower:
                image.append(kind)
            elif names & _IMAGE_INPUTS and any(token in lower for token in _EDIT_TOKENS):
                image.append(kind)
            if "mask" in lower or "inpaint" in lower or names & _MASK_INPUTS:
                mask.append(kind)
            if any(token in lower for token in _CONTROL_TOKENS):
                control.append(kind)

    loader_count = classes.count("XCICQueueJobLoader")
    if raw is not None and loader_count != 1:
        blockers.append("Expected exactly one XCICQueueJobLoader node.")
    if raw is not None and not image:
        blockers.append("No source-image/editing node detected in the configured workflow.")
    if raw is not None and not mask:
        blockers.append("No mask or inpainting path detected.")
    if raw is not None and not control:
        blockers.append("No spatial-control node detected.")
    blockers.append(
        "Node inventory does not validate connected paths, edit-model compatibility, "
        "source/mask provenance, 16 GB VRAM suitability or execution; "
        "guided correction must remain unavailable."
    )
    return SpatialGuidanceInspection(
        workflow_path=path,
        workflow_available=isinstance(raw, dict),
        loader_count=loader_count,
        image_nodes=tuple(sorted(set(image))),
        mask_nodes=tuple(sorted(set(mask))),
        control_nodes=tuple(sorted(set(control))),
        blockers=tuple(dict.fromkeys(blockers)),
    )
