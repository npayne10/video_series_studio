"""Current-authority LTX backend with governed provider execution segmentation.

Segmentation is provider adaptation only.  The governed Shot frame count and FPS
remain unchanged in the authoritative Production Package; the derived execution
plan describes smaller provider work units and their continuity/assembly contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vscs.application.production_execution import CompiledProductionPackage

from .current_authority_backend import (
    CurrentAuthorityLTX23V721ProductionPackageCompilationService as _CurrentPackageCompiler,
)
from .current_authority_backend import (
    LocalComfyUIProductionExecutionBackend as _CurrentAuthorityBackend,
)
from .provider_segmentation import GovernedProviderSegmentationPlanner


class SegmentedLTX23V721ProductionPackageCompilationService(_CurrentPackageCompiler):
    """Emit a deterministic provider execution plan beside governed render authority."""

    def _comfyui_payload(self, compiled: CompiledProductionPackage) -> dict[str, Any]:
        content = super()._comfyui_payload(compiled)
        content["provider_execution_plan"] = GovernedProviderSegmentationPlanner().plan(
            frame_count=compiled.frame_count,
            frames_per_second=compiled.frames_per_second,
            seed=compiled.seed,
        )
        self._refresh_manifest_fingerprint(content)
        return content


class LocalComfyUIProductionExecutionBackend(_CurrentAuthorityBackend):
    """Current-authority backend prepared for automatic segmented LTX execution."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path | None,
        managed_media_directory: str = "Media Output",
        lease_duration_seconds: float = 120.0,
    ) -> None:
        super().__init__(
            project_directory,
            endpoint=endpoint,
            comfyui_output_directory=comfyui_output_directory,
            managed_media_directory=managed_media_directory,
            lease_duration_seconds=lease_duration_seconds,
        )
        self.package_compilation = SegmentedLTX23V721ProductionPackageCompilationService(
            self.project_directory
        )
