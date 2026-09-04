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
    def INPUT_TYPES(cls) -> dict[str, Any]:
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

        primary = self._load_image(primary_record)
        images: list[torch.Tensor] = []
        strengths: list[float] = []
        for record in slots:
            if record is None:
                images.append(primary)
                strengths.append(0.0)
            else:
                images.append(self._load_image(record))
                strengths.append(float(reference_guide_strength))

        continuity_raw = contract.get("continuity")
        if isinstance(continuity_raw, dict) and str(continuity_raw.get("path") or "").strip():
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


NODE_CLASS_MAPPINGS = {
    "VSCSMultiReferenceResolverV721": VSCSMultiReferenceResolverV721,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VSCSMultiReferenceResolverV721": "VSCS Governed Multi-Reference Resolver v7.2.1",
}
