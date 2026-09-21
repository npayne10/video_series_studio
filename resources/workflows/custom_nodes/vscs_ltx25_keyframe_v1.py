"""ComfyUI governed-keyframe package loader for VSCS LTX-2.5 Candidate C."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image


class VSCSLTX25GovernedKeyframePackageLoaderV1:
    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "production_package": ("STRING", {"default": ""}),
                "strict_validation": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = (
        "IMAGE",
        "STRING",
        "STRING",
        "INT",
        "INT",
        "INT",
        "INT",
        "FLOAT",
        "INT",
        "STRING",
        "FLOAT",
        "FLOAT",
    )
    RETURN_NAMES = (
        "governed_keyframe",
        "motion_prompt",
        "negative_prompt",
        "width",
        "height",
        "provider_frame_count",
        "governed_frame_count",
        "fps",
        "seed",
        "filename_prefix",
        "cfg",
        "keyframe_strength",
    )
    FUNCTION = "load"
    CATEGORY = "VSCS/Production"

    def load(
        self,
        production_package: str,
        strict_validation: bool,
    ) -> tuple[torch.Tensor, str, str, int, int, int, int, float, int, str, float, float]:
        path = Path(production_package).expanduser().resolve(strict=False)
        if not path.is_file():
            raise ValueError(f"VSCS LTX-2.5 Production Package does not exist: {path}")
        try:
            root = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"VSCS LTX-2.5 Production Package is invalid JSON: {exc}") from exc
        if not isinstance(root, dict):
            raise ValueError("VSCS LTX-2.5 Production Package root must be an object")
        if root.get("schema_version") != "7.2.2-vscs-1":
            raise ValueError("VSCS Production Package is not an LTX-2.5 governed-keyframe package")

        rebaseline = root.get("provider_video_rebaseline")
        if not isinstance(rebaseline, dict) or rebaseline.get("active_candidate") != "C":
            raise ValueError("LTX-2.5 execution requires active provider Candidate C")

        keyframe = root.get("governed_keyframe")
        if not isinstance(keyframe, dict):
            raise ValueError("LTX-2.5 execution requires governed_keyframe authority")
        if keyframe.get("status") != "approved":
            raise ValueError("Governed Shot Composition Keyframe is not approved")
        keyframe_path = Path(str(keyframe.get("image_path") or "")).expanduser()
        if not keyframe_path.is_absolute():
            keyframe_path = path.parent / keyframe_path
        keyframe_path = keyframe_path.resolve(strict=False)
        if not keyframe_path.is_file():
            raise ValueError(f"Governed Shot Composition Keyframe does not exist: {keyframe_path}")

        expected_sha = str(keyframe.get("image_sha256") or "").strip().lower()
        actual_sha = self._sha256(keyframe_path)
        if strict_validation and (not expected_sha or expected_sha != actual_sha):
            raise ValueError("Governed Shot Composition Keyframe checksum mismatch")

        governed_width = int(root.get("width") or 0)
        governed_height = int(root.get("height") or 0)
        with Image.open(keyframe_path) as source:
            if strict_validation and source.size != (governed_width, governed_height):
                raise ValueError(
                    "Governed Shot Composition Keyframe dimensions do not match "
                    f"the governed render size: {source.size} != "
                    f"{(governed_width, governed_height)}"
                )
            image = source.convert("RGB")
            array = np.asarray(image, dtype=np.float32) / 255.0
        tensor = torch.from_numpy(array)[None, ...]

        governed_frames = int(root.get("frame_count") or 0)
        provider_plan = root.get("provider_execution_plan")
        provider_frames = (
            int(provider_plan.get("provider_frame_count") or 0)
            if isinstance(provider_plan, dict)
            else 0
        )
        values = {
            "motion_prompt": str(root.get("motion_prompt") or "").strip(),
            "negative_prompt": str(root.get("negative_prompt") or "").strip(),
            "width": governed_width,
            "height": governed_height,
            "provider_frames": provider_frames,
            "governed_frames": governed_frames,
            "fps": float(root.get("fps") or 0),
            "seed": int(root.get("seed") or 0),
            "filename_prefix": str(root.get("filename_prefix") or "").strip(),
            "cfg": float(root.get("cfg") or 1.0),
            "keyframe_strength": float(root.get("keyframe_strength") or 0.9),
        }
        if strict_validation:
            missing = [
                name
                for name, value in values.items()
                if value in ("", 0, 0.0)
                and name not in {"seed"}
            ]
            if missing:
                raise ValueError(
                    "VSCS LTX-2.5 Production Package is missing required values: "
                    + ", ".join(missing)
                )
            if values["provider_frames"] % 8 != 1:
                raise ValueError("LTX-2.5 provider frame count must satisfy 1 + 8n")
        return (
            tensor,
            values["motion_prompt"],
            values["negative_prompt"],
            values["width"],
            values["height"],
            values["provider_frames"],
            values["governed_frames"],
            values["fps"],
            values["seed"],
            values["filename_prefix"],
            values["cfg"],
            values["keyframe_strength"],
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


NODE_CLASS_MAPPINGS = {
    "VSCSLTX25GovernedKeyframePackageLoaderV1": VSCSLTX25GovernedKeyframePackageLoaderV1,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "VSCSLTX25GovernedKeyframePackageLoaderV1": (
        "VSCS LTX-2.5 Governed Keyframe Package Loader v1"
    ),
}
