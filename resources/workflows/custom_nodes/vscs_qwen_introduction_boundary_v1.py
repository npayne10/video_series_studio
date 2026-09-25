"""ComfyUI loader for VSCS automated introduction-boundary synthesis."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image


class VSCSIntroductionBoundaryPackageLoaderV1:
    """Load one checksum-pinned source boundary plus one canonical introduced reference."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:  # noqa: N802
        return {
            "required": {
                "request_file": ("STRING", {"default": ""}),
                "strict_validation": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = (
        "IMAGE",
        "IMAGE",
        "STRING",
        "STRING",
        "STRING",
        "STRING",
        "INT",
        "BOOLEAN",
    )
    RETURN_NAMES = (
        "source_boundary",
        "introduced_reference",
        "positive_prompt",
        "negative_prompt",
        "output_directory",
        "output_filename",
        "seed",
        "enable_lightning_lora",
    )
    FUNCTION = "load"
    CATEGORY = "VSCS/Production"

    def load(
        self,
        request_file: str,
        strict_validation: bool,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        str,
        str,
        str,
        str,
        int,
        bool,
    ]:
        request_path = Path(request_file).expanduser().resolve(strict=False)
        if not request_path.is_file():
            raise ValueError(
                f"VSCS automated introduction-boundary request does not exist: {request_path}"
            )
        try:
            raw = json.loads(request_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"VSCS automated introduction-boundary request is invalid JSON: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ValueError("VSCS automated introduction-boundary request must be an object")
        if str(raw.get("schema_version") or "1.0") != "1.0":
            raise ValueError("Unsupported VSCS automated introduction-boundary schema")

        source_path = self._project_file(
            raw,
            "source_boundary_image_path",
            request_path,
        )
        introduced_paths = raw.get("introduced_reference_paths")
        introduced_sha = raw.get("introduced_reference_sha256")
        if not isinstance(introduced_paths, list) or len(introduced_paths) != 1:
            raise ValueError(
                "One synthesis pass requires exactly one introduced canonical reference"
            )
        if not isinstance(introduced_sha, list) or len(introduced_sha) != 1:
            raise ValueError(
                "One synthesis pass requires exactly one introduced reference checksum"
            )
        introduced_path = Path(str(introduced_paths[0])).expanduser()
        if not introduced_path.is_absolute():
            introduced_path = request_path.parent / introduced_path
        introduced_path = introduced_path.resolve(strict=False)
        if not introduced_path.is_file():
            raise ValueError(
                f"Introduced canonical reference does not exist: {introduced_path}"
            )

        if strict_validation:
            expected_source = str(raw.get("source_boundary_image_sha256") or "").strip().lower()
            if not expected_source or self._sha256(source_path) != expected_source:
                raise ValueError("Source boundary image checksum mismatch")
            expected_reference = str(introduced_sha[0] or "").strip().lower()
            if not expected_reference or self._sha256(introduced_path) != expected_reference:
                raise ValueError("Introduced canonical reference checksum mismatch")

        source = self._load_rgb(source_path)
        introduced = self._load_rgb(introduced_path)
        positive = str(raw.get("positive_prompt") or "").strip()
        negative = str(raw.get("negative_prompt") or "").strip()
        output_directory = str(raw.get("output_directory") or "").strip()
        output_filename = str(raw.get("output_filename") or "").strip()
        seed = int(raw.get("seed") or 0)
        enable_lightning = bool(raw.get("enable_lightning_lora", True))
        if strict_validation:
            if not positive or not negative:
                raise ValueError("Automated introduction-boundary prompts cannot be blank")
            if not output_directory or not output_filename:
                raise ValueError("Automated introduction-boundary output path is incomplete")
            width = int(raw.get("width") or 0)
            height = int(raw.get("height") or 0)
            if width <= 0 or height <= 0:
                raise ValueError("Automated introduction-boundary dimensions must be positive")
            if int(source.shape[2]) != width or int(source.shape[1]) != height:
                raise ValueError(
                    "Source boundary dimensions do not match governed render geometry"
                )
        return (
            source,
            introduced,
            positive,
            negative,
            output_directory,
            output_filename,
            seed,
            enable_lightning,
        )

    @staticmethod
    def _project_file(raw: dict[str, Any], key: str, request_path: Path) -> Path:
        path = Path(str(raw.get(key) or "")).expanduser()
        if not path.is_absolute():
            path = request_path.parent / path
        resolved = path.resolve(strict=False)
        if not resolved.is_file():
            raise ValueError(f"{key} does not exist: {resolved}")
        return resolved

    @staticmethod
    def _load_rgb(path: Path) -> torch.Tensor:
        with Image.open(path) as source:
            image = source.convert("RGB")
            array = np.asarray(image, dtype=np.float32) / 255.0
        return torch.from_numpy(array)[None, ...]

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


NODE_CLASS_MAPPINGS = {
    "VSCSIntroductionBoundaryPackageLoaderV1": VSCSIntroductionBoundaryPackageLoaderV1,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "VSCSIntroductionBoundaryPackageLoaderV1": (
        "VSCS Automated Introduction Boundary Loader v1"
    ),
}
