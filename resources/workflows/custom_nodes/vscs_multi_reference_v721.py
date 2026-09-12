"""ComfyUI resolver for VSCS LTX 2.3 governed multi-reference packages.

Deploy this file into ComfyUI/custom_nodes. It keeps up to three governed references
separate and supplies individual IMAGE tensors and per-slot guide strengths to the
LTX Ingredients IC-LoRA guide chain. Segment continuity is exposed independently.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image

_ROLE_TO_SLOT = {
    "primary_identity": 0,
    "secondary_identity": 1,
    "group_identity": 1,
    "environment_reference": 2,
}


class VSCSMultiReferenceResolverV721:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "reference_plan_json": ("STRING", {"forceInput": True}),
                "target_description": ("STRING", {"forceInput": True}),
                "target_width": ("INT", {"forceInput": True}),
                "target_height": ("INT", {"forceInput": True}),
                "reference_guide_strength": ("FLOAT", {"forceInput": True}),
                "strict_validation": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = (
        "IMAGE",
        "IMAGE",
        "IMAGE",
        "FLOAT",
        "FLOAT",
        "FLOAT",
        "IMAGE",
        "BOOLEAN",
    )
    RETURN_NAMES = (
        "primary_identity",
        "secondary_identity",
        "environment_reference",
        "primary_strength",
        "secondary_strength",
        "environment_strength",
        "continuity_image",
        "continuity_bypass",
    )
    FUNCTION = "resolve"
    CATEGORY = "VSCS/Production"

    def resolve(
        self,
        reference_plan_json: str,
        target_description: str,
        target_width: int,
        target_height: int,
        reference_guide_strength: float,
        strict_validation: bool,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, float, float, float, torch.Tensor, bool]:
        del target_description, target_width, target_height
        plan = self._decode_plan(reference_plan_json)
        contract = plan.get("provider_multi_reference")
        if not isinstance(contract, dict) or contract.get("mode") != "ltx_ingredients_iclora":
            raise ValueError("VSCS provider_multi_reference contract is missing or unsupported")

        raw_references = contract.get("references")
        if not isinstance(raw_references, list) or not raw_references:
            raise ValueError("VSCS provider_multi_reference contract has no references")

        slots: list[dict[str, Any] | None] = [None, None, None]
        for raw in raw_references:
            if not isinstance(raw, dict):
                continue
            role = str(raw.get("role") or "")
            slot = _ROLE_TO_SLOT.get(role)
            if slot is None:
                slot_number = raw.get("slot")
                if isinstance(slot_number, int) and 1 <= slot_number <= 3:
                    slot = slot_number - 1
            if slot is None:
                if strict_validation:
                    raise ValueError(f"Unsupported governed LTX reference role: {role!r}")
                continue
            if slots[slot] is not None and strict_validation:
                raise ValueError(f"Duplicate governed LTX reference slot: {slot + 1}")
            slots[slot] = raw

        primary_record = slots[0] or next(
            (item for item in slots if item is not None),
            None,
        )
        if primary_record is None:
            raise ValueError("VSCS multi-reference contract cannot resolve a primary reference")

        continuity_raw = contract.get("continuity")
        has_continuity = isinstance(continuity_raw, dict) and bool(
            str(continuity_raw.get("path") or "").strip()
        )

        primary = self._load_image(primary_record)
        images: list[torch.Tensor] = []
        strengths: list[float] = []
        for record in slots:
            if record is None:
                images.append(primary)
                strengths.append(0.0)
            else:
                images.append(self._load_image(record))
                weight_key = "continuation_weight" if has_continuity else "weight"
                raw_weight = record.get(weight_key, record.get("weight", 1.0))
                try:
                    weight = float(raw_weight)
                except (TypeError, ValueError) as exc:
                    if strict_validation:
                        raise ValueError(
                            f"Governed LTX reference has invalid {weight_key}: {raw_weight!r}"
                        ) from exc
                    weight = 1.0
                if not 0.0 <= weight <= 1.0:
                    if strict_validation:
                        raise ValueError(
                            f"Governed LTX reference {weight_key} must be between 0 and 1"
                        )
                    weight = min(max(weight, 0.0), 1.0)
                strengths.append(float(reference_guide_strength) * weight)

        if has_continuity:
            continuity = self._load_image(continuity_raw)
            continuity_bypass = False
        else:
            continuity = primary
            continuity_bypass = True

        return (
            images[0],
            images[1],
            images[2],
            strengths[0],
            strengths[1],
            strengths[2],
            continuity,
            continuity_bypass,
        )

    @staticmethod
    def _decode_plan(value: str) -> dict[str, Any]:
        try:
            raw = json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"VSCS reference plan is not valid JSON: {exc}") from exc
        if not isinstance(raw, dict):
            raise ValueError("VSCS reference plan root must be an object")
        return raw

    @staticmethod
    def _load_image(record: dict[str, Any]) -> torch.Tensor:
        raw_path = str(record.get("path") or "").strip()
        if not raw_path:
            raise ValueError("Governed LTX reference has no path")
        path = Path(raw_path).expanduser().resolve(strict=False)
        if not path.is_file():
            raise ValueError(f"Governed LTX reference does not exist: {path}")
        with Image.open(path) as source:
            image = source.convert("RGB")
            array = np.asarray(image, dtype=np.float32) / 255.0
        return torch.from_numpy(array)[None, ...]


class VSCSContinuityPromptV721:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "shot_prompt": ("STRING", {"forceInput": True}),
                "reference_plan_json": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("conditioned_shot_prompt",)
    FUNCTION = "compose"
    CATEGORY = "VSCS/Production"

    def compose(self, shot_prompt: str, reference_plan_json: str) -> tuple[str]:
        plan = VSCSMultiReferenceResolverV721._decode_plan(reference_plan_json)
        contract = plan.get("provider_multi_reference")
        if not isinstance(contract, dict):
            return (shot_prompt,)

        references = contract.get("references")
        role_text: list[str] = []
        if isinstance(references, list):
            for raw in references:
                if not isinstance(raw, dict):
                    continue
                role = str(raw.get("role") or "").strip()
                label = str(
                    raw.get("label") or raw.get("asset_id") or raw.get("reference_id") or ""
                ).strip()
                if role and label:
                    if role == "environment_reference":
                        role_text.append(
                            f"{role}={label} (supporting appearance reference only; "
                            "do not use as foreground composition or replace the governed set)"
                        )
                    else:
                        role_text.append(f"{role}={label} (preserve this person's identity)")

        continuity = contract.get("continuity")
        has_continuity = isinstance(continuity, dict) and bool(
            str(continuity.get("path") or "").strip()
        )
        prompt_mode = (
            str(continuity.get("prompt_mode") or "").strip() if isinstance(continuity, dict) else ""
        )
        if has_continuity and prompt_mode == "preserve_shot_to_shot_continuity":
            prefix = (
                "Use the supplied previous approved Shot final frame as visual continuity "
                "authority for identity, wardrobe, environment, lighting state and spatial "
                "orientation. Obey the new governed Shot description and camera direction; "
                "do not force the previous framing or pretend this is the same continuous shot. "
            )
        elif has_continuity:
            prefix = (
                "Continue the exact same cinematic shot from the supplied previous-segment final "
                "frame. Preserve camera position, lens, framing, people, wardrobe, lighting, "
                "environment, spatial relationships and action direction. Do not restart, re-stage "
                "or introduce new people. "
            )
        else:
            prefix = "Begin one coherent cinematic shot from the governed scene description. "
        roles = "Reference roles: " + "; ".join(role_text) + ". " if role_text else ""
        composition = (
            "Identity references control who the people are, not where they are placed. "
            "Environment references control appearance only and must remain subordinate to the "
            "governed shot description and continuity frame. "
        )
        return (f"{prefix}{roles}{composition}{shot_prompt}".strip(),)


NODE_CLASS_MAPPINGS = {
    "VSCSMultiReferenceResolverV721": VSCSMultiReferenceResolverV721,
    "VSCSContinuityPromptV721": VSCSContinuityPromptV721,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VSCSMultiReferenceResolverV721": "VSCS Governed Multi-Reference Resolver v7.2.1",
    "VSCSContinuityPromptV721": "VSCS Continuity Prompt Authority v7.2.1",
}


class VSCSProviderFrameCountV721:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "governed_frame_count": ("INT", {"forceInput": True}),
                "frame_modulus": ("INT", {"default": 8, "min": 1, "max": 64}),
                "frame_offset": ("INT", {"default": 1, "min": 0, "max": 63}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("provider_frame_count",)
    FUNCTION = "resolve"
    CATEGORY = "VSCS/Production"

    def resolve(
        self,
        governed_frame_count: int,
        frame_modulus: int,
        frame_offset: int,
    ) -> tuple[int]:
        if governed_frame_count <= 0:
            raise ValueError("Governed frame count must be positive")
        if frame_modulus <= 0:
            raise ValueError("Provider frame modulus must be positive")
        candidate = governed_frame_count
        while (candidate - frame_offset) % frame_modulus != 0:
            candidate += 1
        return (candidate,)


class VSCSGovernedOutputNormalizerV721:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "images": ("IMAGE", {"forceInput": True}),
                "governed_width": ("INT", {"forceInput": True}),
                "governed_height": ("INT", {"forceInput": True}),
                "governed_frame_count": ("INT", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("governed_images",)
    FUNCTION = "normalize"
    CATEGORY = "VSCS/Production"

    def normalize(
        self,
        images: torch.Tensor,
        governed_width: int,
        governed_height: int,
        governed_frame_count: int,
    ) -> tuple[torch.Tensor]:
        if images.ndim != 4:
            raise ValueError("Decoded video IMAGE tensor must be BHWC")
        if governed_width <= 0 or governed_height <= 0 or governed_frame_count <= 0:
            raise ValueError("Governed output dimensions and frame count must be positive")
        if images.shape[0] < governed_frame_count:
            raise ValueError("Provider output contains fewer frames than governed Shot authority")

        images = images[:governed_frame_count]
        source_height = int(images.shape[1])
        source_width = int(images.shape[2])
        if source_width == governed_width and source_height == governed_height:
            return (images,)

        scale = min(
            governed_width / source_width,
            governed_height / source_height,
        )
        scaled_width = max(1, min(governed_width, round(source_width * scale)))
        scaled_height = max(1, min(governed_height, round(source_height * scale)))
        channels_first = images.permute(0, 3, 1, 2)
        resized = torch.nn.functional.interpolate(
            channels_first,
            size=(scaled_height, scaled_width),
            mode="bilinear",
            align_corners=False,
        ).permute(0, 2, 3, 1)

        output = torch.zeros(
            (
                governed_frame_count,
                governed_height,
                governed_width,
                int(images.shape[3]),
            ),
            dtype=resized.dtype,
            device=resized.device,
        )
        top = (governed_height - scaled_height) // 2
        left = (governed_width - scaled_width) // 2
        output[
            :,
            top : top + scaled_height,
            left : left + scaled_width,
            :,
        ] = resized
        return (output,)


class VSCSProviderGeometryV721:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "governed_width": ("INT", {"forceInput": True}),
                "governed_height": ("INT", {"forceInput": True}),
                "alignment": ("INT", {"default": 32, "min": 1, "max": 512}),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("provider_width", "provider_height")
    FUNCTION = "resolve"
    CATEGORY = "VSCS/Production"

    def resolve(
        self,
        governed_width: int,
        governed_height: int,
        alignment: int,
    ) -> tuple[int, int]:
        if governed_width <= 0 or governed_height <= 0:
            raise ValueError("Governed production geometry must be positive")
        if alignment <= 0:
            raise ValueError("Provider geometry alignment must be positive")
        width = governed_width - (governed_width % alignment)
        height = governed_height - (governed_height % alignment)
        if width <= 0 or height <= 0:
            raise ValueError("Provider-aligned production geometry must be positive")
        return width, height


NODE_CLASS_MAPPINGS["VSCSProviderGeometryV721"] = VSCSProviderGeometryV721
NODE_CLASS_MAPPINGS["VSCSProviderFrameCountV721"] = VSCSProviderFrameCountV721
NODE_CLASS_MAPPINGS["VSCSGovernedOutputNormalizerV721"] = VSCSGovernedOutputNormalizerV721
NODE_DISPLAY_NAME_MAPPINGS["VSCSProviderGeometryV721"] = "VSCS Provider Geometry Adapter v7.2.1"
NODE_DISPLAY_NAME_MAPPINGS["VSCSProviderFrameCountV721"] = (
    "VSCS Provider Frame Count Adapter v7.2.1"
)
NODE_DISPLAY_NAME_MAPPINGS["VSCSGovernedOutputNormalizerV721"] = (
    "VSCS Governed Output Normalizer v7.2.1"
)
