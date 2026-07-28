"""Central configuration for the external XCIC rendering installation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class XCICConfiguration:
    """Resolve the shared XCIC installation used by all VSCS projects."""

    installation_root: Path
    comfyui_url: str
    text_workflow_path: Path
    text_mapping_path: Path
    text_profile_path: Path

    @classmethod
    def load(cls) -> "XCICConfiguration":
        root = Path(os.environ.get("VSCS_XCIC_ROOT", r"D:\VSCS\XCIC"))
        explicit_workflow = os.environ.get("VSCS_XCIC_TEXT_WORKFLOW")
        if explicit_workflow:
            workflow = Path(explicit_workflow)
        else:
            loader_workflow = root / "Xorix_Qwen_XCIC_Image_Creator_v1.0.json"
            workflow = loader_workflow if loader_workflow.is_file() else root / "qwen_xcic_api_workflow.json"
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
        if not self.text_workflow_path.expanduser().is_file():
            raise FileNotFoundError(
                "XCIC text-to-image workflow is missing. Place the loader-based workflow at "
                f"{self.installation_root / 'Xorix_Qwen_XCIC_Image_Creator_v1.0.json'} "
                "or set VSCS_XCIC_TEXT_WORKFLOW explicitly."
            )
