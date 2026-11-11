"""F5.4.1B isolated experimental mask-aware Qwen API graph qualification.

PREPARATION AND INSPECTION ONLY. No provider submission, CAP service, reference
registration or correction attempt. The mask loader must be bound to a reviewed
ComfyUI input filename before any future isolated execution.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path


class MaskAwareQualificationError(RuntimeError):
    """Experimental spatial graph or mask is not valid for qualification."""


_MASK = "F541B_MASK"
_LATENT = "F541B_LATENT_MASK"
_COMPOSITE = "F541B_COMPOSITE"
_MASK_PLACEHOLDER = "__F541B_REVIEWED_COMFYUI_INPUT_MASK_FILENAME__"
_OUTPUT = "9"
_SAMPLER = "170:169"
_VAE = "170:156"
_DECODE = "170:158"
_SOURCE = "170:160"


@dataclass(frozen=True, slots=True)
class MaskAwareQualification:
    template_sha256: str
    experimental_graph_sha256: str
    source_dimensions: tuple[int, int]
    mask_sha256: str
    mask_coverage_percent: float
    mask_bounds: tuple[int, int, int, int]
    mask_comfyui_input_bound: bool
    graph_nodes_validated_live: bool = False
    gpu_inference_verified: bool = False
    outside_mask_pixels_verified: bool = False

    @property
    def execution_authorized(self) -> bool:
        return False


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _source_size(path: Path) -> tuple[int, int]:
    if not path.is_file() or path.is_symlink() or path.suffix.lower() != ".png":
        raise MaskAwareQualificationError("Source must be an existing non-symlink PNG")
    try:
        with Image.open(path) as source:
            if source.format != "PNG" or source.width < 256 or source.height < 256:
                raise MaskAwareQualificationError("Source image is not a usable PNG")
            if source.width * source.height > 32_000_000:
                raise MaskAwareQualificationError("Source dimensions exceed limit")
            return source.size
    except (OSError, ValueError) as exc:
        raise MaskAwareQualificationError("Cannot inspect source PNG") from exc


def create_binary_edit_mask(
    source_png: Path, mask_path: Path, bounds: tuple[int, int, int, int]
) -> MaskAwareQualification:
    """Create an offline, deliberately bounded mask (white=edit, black=protect)."""
    width, height = _source_size(source_png)
    x0, y0, x1, y1 = bounds
    if (
        any(type(v) is not int for v in bounds)
        or not 0 <= x0 < x1 <= width
        or not 0 <= y0 < y1 <= height
    ):
        raise MaskAwareQualificationError("Mask ROI must be within the original source")
    coverage = 100.0 * (x1 - x0) * (y1 - y0) / (width * height)
    if not 0.01 <= coverage <= 25:
        raise MaskAwareQualificationError("Edit region must occupy 0.01%-25% of source")
    if mask_path.exists() or mask_path.is_symlink():
        raise MaskAwareQualificationError("Mask evidence already exists")
    if not mask_path.parent.is_dir():
        raise MaskAwareQualificationError("Create external acceptance directory first")
    mask = Image.new("L", (width, height), 0)
    mask.paste(255, (x0, y0, x1, y1))
    mask.save(mask_path, format="PNG")
    raw = mask_path.read_bytes()
    return MaskAwareQualification(
        template_sha256=_sha(default_workflow_path().read_bytes()),
        experimental_graph_sha256="",
        source_dimensions=(width, height),
        mask_sha256=_sha(raw),
        mask_coverage_percent=round(coverage, 4),
        mask_bounds=bounds,
        mask_comfyui_input_bound=False,
    )


def build_experimental_masked_graph(
    *, workflow_path: Path | None = None, mask_input_filename: str = _MASK_PLACEHOLDER
) -> dict[str, Any]:
    """Create a separate derived graph, never change trusted managed workflow."""
    template = workflow_path if workflow_path is not None else default_workflow_path()
    inspect_managed_qwen_edit_workflow(template)
    graph: dict[str, Any] = copy.deepcopy(json.loads(template.read_text(encoding="utf-8")))
    if not mask_input_filename or "/" in mask_input_filename or "\\" in mask_input_filename:
        raise MaskAwareQualificationError("Mask input must be a plain ComfyUI input filename")
    if mask_input_filename not in {_MASK_PLACEHOLDER} and not mask_input_filename.endswith(".png"):
        raise MaskAwareQualificationError("Mask input must be PNG")
    graph[_MASK] = {
        "class_type": "LoadImageMask",
        "inputs": {"image": mask_input_filename, "channel": "red"},
    }
    graph[_LATENT] = {
        "class_type": "SetLatentNoiseMask",
        "inputs": {"samples": [_VAE, 0], "mask": [_MASK, 0]},
    }
    graph[_SAMPLER]["inputs"]["latent_image"] = [_LATENT, 0]
    graph[_COMPOSITE] = {
        "class_type": "ImageCompositeMasked",
        "inputs": {
            "destination": [_SOURCE, 0],
            "source": [_DECODE, 0],
            "mask": [_MASK, 0],
            "x": 0,
            "y": 0,
            "resize_source": False,
        },
    }
    graph[_OUTPUT]["inputs"]["images"] = [_COMPOSITE, 0]
    return graph


def validate_experimental_graph(graph: dict[str, Any]) -> None:
    """Validate full experimental topology against unchanged trusted graph."""
    inspect = inspect_managed_qwen_edit_workflow(default_workflow_path())
    template: dict[str, Any] = json.loads(inspect.workflow_path.read_text(encoding="utf-8"))
    mask_node = graph.get(_MASK)
    if not isinstance(mask_node, dict):
        raise MaskAwareQualificationError("Experimental mask loader missing")
    mask_inputs = mask_node.get("inputs")
    if not isinstance(mask_inputs, dict):
        raise MaskAwareQualificationError("Experimental mask loader inputs invalid")
    filename = mask_inputs.get("image")
    if not isinstance(filename, str):
        raise MaskAwareQualificationError("Mask filename invalid")
    expected = build_experimental_masked_graph(mask_input_filename=filename)
    if graph != expected:
        raise MaskAwareQualificationError("Experimental graph has an unreviewed change")
    if template[_SAMPLER]["inputs"]["denoise"] != 1:
        raise MaskAwareQualificationError("Trusted sampler denoise baseline changed")


def confirm_preserved_pixels(
    source_png: Path, composite_png: Path, mask_png: Path
) -> dict[str, Any]:
    """Measure exact RGB preservation OUTSIDE the specified binary mask."""
    paths = (source_png, composite_png, mask_png)
    if any(not p.is_file() or p.is_symlink() or p.suffix.lower() != ".png" for p in paths):
        raise MaskAwareQualificationError("Missing/non-PNG or symlinked comparison evidence")
    with (
        Image.open(source_png) as original,
        Image.open(composite_png) as result,
        Image.open(mask_png) as mask,
    ):
        if (
            original.size != result.size
            or original.size != mask.size
            or mask.mode != "L"
            or set(mask.getdata()) != {0, 255}
        ):
            raise MaskAwareQualificationError("Images must match and mask be binary")
        left = original.convert("RGB")
        right = result.convert("RGB")
        protected = mask.point(lambda p: 255 if p == 0 else 0)
        diff = ImageChops.difference(left, right).convert("RGB")
        changed = diff.convert("L").point(lambda p: 255 if p else 0)
        protected_changes = ImageChops.multiply(changed, protected)
        histogram = protected_changes.histogram()
        changed_count = histogram[255]
        protected_count = protected.histogram()[255]
        permitted_count = original.width * original.height - protected_count
    return {
        "source_sha256": _sha(source_png.read_bytes()),
        "composite_sha256": _sha(composite_png.read_bytes()),
        "mask_sha256": _sha(mask_png.read_bytes()),
        "protected_pixels": protected_count,
        "protected_changed_pixels": changed_count,
        "editable_pixels": permitted_count,
        "outside_mask_pixels_identical": changed_count == 0,
        "semantic_geometry_correct": None,
        "execution_authorized": False,
    }
