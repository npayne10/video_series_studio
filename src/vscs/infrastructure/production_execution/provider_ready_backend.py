"""Phase 20.15.1a corrections layered over profile-scoped production execution."""

from __future__ import annotations

from pathlib import Path

from .profile_scoped_backend import (
    LocalComfyUIProductionExecutionBackend as _ProfileScopedProductionExecutionBackend,
)


class LocalComfyUIProductionExecutionBackend(_ProfileScopedProductionExecutionBackend):
    """Use the real ComfyUI output root for history-relative output reconciliation."""

    def _require_comfyui_output_directory(self) -> Path:
        configured = super()._require_comfyui_output_directory()
        if configured.name.casefold() == "output":
            return configured
        for parent in configured.parents:
            if parent.name.casefold() == "output" and parent.is_dir():
                return parent
        return configured
