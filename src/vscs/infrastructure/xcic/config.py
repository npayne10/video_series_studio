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
        return cls(
            installation_root=root,
            comfyui_url=os.environ.get("VSCS_COMFYUI_URL", "http://127.0.0.1:8188"),
            text_workflow_path=Path(
                os.environ.get(
                    "VSCS_XCIC_TEXT_WORKFLOW",
                    str(root / "qwen_xcic_api_workflow.json"),
                )
            ),
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
        missing = [
            path
            for path in (
                self.text_workflow_path,
                self.text_mapping_path,
                self.text_profile_path,
            )
            if not path.expanduser().is_file()
        ]
        if missing:
            formatted = "\n".join(f"- {path}" for path in missing)
            raise FileNotFoundError(
                "XCIC text-to-image configuration is incomplete. Expected files under "
                f"{self.installation_root}:\n{formatted}"
            )
