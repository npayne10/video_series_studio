"""F5.4.1: read-only Qwen spatial edit capability and fidelity inspection.

This is NOT inpainting, mask guidance, CAP approval, or provider execution.
It inspects the exact managed graph and optionally measures image-level
differences in a separate independent pair of PNG files.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageStat

from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path


class QwenSpatialFidelityError(RuntimeError):
    """Fidelity evidence is missing, incompatible or unsafe."""


@dataclass(frozen=True, slots=True)
class QwenSpatialFidelityAssessment:
    workflow_sha256: str
    sampler_denoise: float
    source_conditioned: bool
    mask_related_node_present: bool
    region_limited_edit_validated: bool
    full_frame_reinterpretation_risk: bool
    source_sha256: str | None
    edited_sha256: str | None
    source_dimensions: tuple[int, int] | None
    edited_dimensions: tuple[int, int] | None
    mean_absolute_rgb_delta: float | None
    changed_pixel_percentage: float | None
    warnings: tuple[str, ...]

    @property
    def execution_authorized(self) -> bool:
        return False

    @property
    def final_attempt_spatially_qualified(self) -> bool:
        return self.region_limited_edit_validated

    def describe(self) -> str:
        lines = [
            "F5.4.1 - Qwen Spatial Edit Fidelity (READ ONLY)",
            f"Managed workflow SHA-256: {self.workflow_sha256}",
            f"Sampler denoise: {self.sampler_denoise:g}",
            f"Source-image conditioned: {self.source_conditioned}",
            f"Mask-related node present: {self.mask_related_node_present}",
            f"Validated mask/inpainting: {self.region_limited_edit_validated}",
            f"Full-frame reinterpretation risk: {self.full_frame_reinterpretation_risk}",
        ]
        if self.source_sha256 is not None:
            lines.extend(
                [
                    f"Source PNG SHA-256: {self.source_sha256}",
                    f"Edited PNG SHA-256: {self.edited_sha256}",
                    f"Source dimensions: {self.source_dimensions}",
                    f"Edited dimensions: {self.edited_dimensions}",
                    f"Mean RGB pixel difference: {self.mean_absolute_rgb_delta}",
                    f"Changed pixels (%): {self.changed_pixel_percentage}",
                ]
            )
        lines.extend(f"WARNING: {warning}" for warning in self.warnings)
        lines.extend(
            [
                "Pixel differences do NOT establish semantic or geometric correctness.",
                "No GPU call, CAP write, Candidate registration or attempt reservation.",
                "An unvalidated mask is NOT sufficient to enable the final attempt.",
            ]
        )
        return "\n".join(lines)


def _image(path: Path) -> tuple[Image.Image, str]:
    if path.is_symlink() or path.suffix.lower() != ".png" or not path.is_file():
        raise QwenSpatialFidelityError("Only existing non-symlink PNG images are accepted")
    raw = path.read_bytes()
    if len(raw) > 40 * 1024 * 1024:
        raise QwenSpatialFidelityError("Image exceeds bounded inspection size")
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or image.width < 256 or image.height < 256:
                raise QwenSpatialFidelityError("Source/edited image is not a valid sized PNG")
            if image.width * image.height > 32_000_000:
                raise QwenSpatialFidelityError("Image exceeds maximum pixel count")
            decoded = image.convert("RGB")
    except (OSError, ValueError) as exc:
        raise QwenSpatialFidelityError("Cannot decode PNG for fidelity inspection") from exc
    return decoded, hashlib.sha256(raw).hexdigest()


def inspect_qwen_spatial_fidelity(
    *,
    workflow_path: Path | None = None,
    source_image: Path | None = None,
    edited_image: Path | None = None,
) -> QwenSpatialFidelityAssessment:
    """Inspect actual graph conditioning and optionally compare complete images."""
    if (source_image is None) != (edited_image is None):
        raise QwenSpatialFidelityError("Source and edited images must be provided together")
    workflow = workflow_path if workflow_path is not None else default_workflow_path()
    validated = inspect_managed_qwen_edit_workflow(workflow)
    try:
        graph = json.loads(workflow.read_text(encoding="utf-8"))
        inputs = graph["170:169"]["inputs"]
        denoise = inputs["denoise"]
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise QwenSpatialFidelityError("Managed sampler cannot be inspected") from exc
    if type(denoise) not in (float, int) or not 0 < denoise <= 1:
        raise QwenSpatialFidelityError("Sampler denoise is not a fixed, bounded value")
    # A non-mask-aware VAEEncode routed directly to KSampler cannot guarantee
    # spatial locality. Do not infer mask support merely from installed nodes.
    nodes: dict[str, Any] = graph
    mask_classes = {
        "VAEEncodeForInpaint",
        "InpaintModelConditioning",
        "SetLatentNoiseMask",
    }
    mask_node_present = any(
        isinstance(node, dict) and node.get("class_type") in mask_classes for node in nodes.values()
    )
    # The existing managed graph has no reviewed mask route. Even a new mask
    # node appearing would need explicit graph validation and an acceptance test.
    validated_mask = False
    warnings: list[str] = []
    if denoise >= 0.95:
        warnings.append("Denoise close to 1 permits major full-image reconstruction")
    if not mask_node_present:
        warnings.append("No mask/inpaint node exists on the checked-in sampler path")
    else:
        warnings.append("Mask-related node detected but its route is NOT validated")
    warnings.append(
        "Source preservation depends on model conditioning; spatial boundaries "
        "are not guaranteed by the current workflow"
    )
    sha_a = sha_b = None
    size_a = size_b = None
    mean_delta = changed_percent = None
    if source_image is not None and edited_image is not None:
        source, sha_a = _image(source_image)
        edited, sha_b = _image(edited_image)
        size_a, size_b = source.size, edited.size
        if source.size == edited.size:
            difference = ImageChops.difference(source, edited)
            mean_delta = round(sum(ImageStat.Stat(difference).mean) / 3, 3)
            changed = difference.convert("L").point(lambda value: 255 if value > 12 else 0)
            histogram = changed.histogram()
            changed_percent = round(100 * histogram[255] / (source.width * source.height), 3)
        else:
            warnings.append(
                "Image dimensions differ; pixelwise fidelity cannot be compared without "
                "resampling, which would distort the evidence"
            )
    return QwenSpatialFidelityAssessment(
        workflow_sha256=validated.workflow_sha256,
        sampler_denoise=float(denoise),
        source_conditioned=True,
        mask_related_node_present=mask_node_present,
        region_limited_edit_validated=validated_mask,
        full_frame_reinterpretation_risk=denoise >= 0.95 or not validated_mask,
        source_sha256=sha_a,
        edited_sha256=sha_b,
        source_dimensions=size_a,
        edited_dimensions=size_b,
        mean_absolute_rgb_delta=mean_delta,
        changed_pixel_percentage=changed_percent,
        warnings=tuple(warnings),
    )
