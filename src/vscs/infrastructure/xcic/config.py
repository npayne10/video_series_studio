"""Central configuration for the external XCIC rendering installation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class XCICConfiguration:
    """Resolve the shared XCIC installation used by all VSCS projects."""

    installation_root: Path
    comfyui_url: str
    text_workflow_path: Path
    text_mapping_path: Path
    text_profile_path: Path

    @classmethod
    def load(cls) -> XCICConfiguration:
        root = Path(os.environ.get("VSCS_XCIC_ROOT", r"D:\VSCS\XCIC"))
        explicit_workflow = os.environ.get("VSCS_XCIC_TEXT_WORKFLOW")
        if explicit_workflow:
            workflow = Path(explicit_workflow)
        else:
            candidates = (
                root / "Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json",
                root / "Xorix_Qwen_XCIC_Image_Creator_v1.0_API.json",
                root / "qwen_xcic_loader_api_workflow.json",
                root / "Xorix_Qwen_XCIC_Image_Creator_v1.0.json",
            )
            workflow = next((path for path in candidates if path.is_file()), candidates[0])
        return cls(
            installation_root=root,
            comfyui_url=os.environ.get("VSCS_COMFYUI_URL", "http://127.0.0.1:8188"),
            text_workflow_path=workflow,
            text_mapping_path=Path(
                os.environ.get(
                    "VSCS_XCIC_TEXT_MAPPING",
                    str(root / "qwen_xcic_mapping.json"),
                )
            ),
            text_profile_path=Path(
                os.environ.get(
                    "VSCS_XCIC_TEXT_PROFILE",
                    str(root / "qwen_xcic_profile.json"),
                )
            ),
        )

    def validate_text_to_image(self) -> None:
        path = self.text_workflow_path.expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                "XCIC text-to-image workflow is missing. Export the loader-based workflow "
                "from ComfyUI using 'Save (API Format)' and save it as:\n"
                f"{self.installation_root / 'Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json'}\n"
                "The API workflow must contain one XCICQueueJobLoader node."
            )
        try:
            value: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unable to read XCIC workflow {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"XCIC workflow must be a JSON object: {path}")
        if "nodes" in value:
            raise ValueError(
                "The configured XCIC workflow is an editable ComfyUI workflow, not an API workflow. "
                "Open it in ComfyUI, choose 'Save (API Format)', and save the result as:\n"
                f"{self.installation_root / 'Xorix_Qwen_XCIC_Image_Creator_v1.0_api.json'}"
            )
        loader_count = sum(
            1
            for node in value.values()
            if isinstance(node, dict) and node.get("class_type") == "XCICQueueJobLoader"
        )
        if loader_count != 1:
            raise ValueError(
                "The XCIC API workflow must contain exactly one XCICQueueJobLoader node; "
                f"found {loader_count} in {path}. Export the same loader-based workflow using "
                "ComfyUI's 'Save (API Format)' command."
            )
