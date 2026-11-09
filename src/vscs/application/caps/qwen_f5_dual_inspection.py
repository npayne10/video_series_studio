"""F5.1: read-only comparison of legacy XCIC and managed Qwen edit graphs.

The legacy text workflow has no source-image control. The managed image-edit
workflow has connected reference conditioning, but not a verified mask path.
This report is informative only and cannot authorize a GPU submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vscs.application.caps.managed_qwen_edit_inspection import (
    ManagedQwenEditError,
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.application.caps.spatial_candidate_guidance import inspect_spatial_guidance
from vscs.infrastructure.xcic.config import XCICConfiguration


@dataclass(frozen=True, slots=True)
class DualWorkflowInspection:
    """Distinct, non-authorizing findings for two different generation paths."""

    legacy_path: Path
    legacy_description: str
    managed_path: Path
    managed_source_conditioned: bool
    managed_workflow_sha256: str | None
    managed_error: str | None

    @property
    def execution_authorized(self) -> bool:
        return False

    def describe(self) -> str:
        lines = [
            "B.5.26F F5.1 — Dual workflow inspection (read-only)",
            "",
            "A. LEGACY XCIC — TEXT-TO-IMAGE",
            self.legacy_description,
            "",
            "B. MANAGED QWEN-IMAGE-EDIT-2511 — SOURCE-CONDITIONED",
            f"Workflow: {self.managed_path}",
        ]
        if self.managed_source_conditioned:
            lines.extend(
                [
                    "Connected source-image edit graph: YES",
                    "Source: XCICQwenReferenceJobLoader -> FluxKontextImageScale",
                    "Conditioning: TextEncodeQwenImageEditPlus",
                    "Checkpoint: Qwen-Image-Edit-2511; Lightning LoRA",
                    "Output: XCICSaveReferenceCandidate",
                    f"Workflow SHA-256: {self.managed_workflow_sha256}",
                    "Validated spatial mask/inpainting: NO",
                    "GPU memory/actual inference: NOT VERIFIED by this inspection",
                ]
            )
        else:
            lines.append(f"Managed workflow invalid: {self.managed_error}")
        lines.extend(
            [
                "",
                "This comparison never contacts ComfyUI or submits a request.",
                "Use 'Check Qwen F5 Hardware Readiness' to check installed nodes,",
                "model inventory and GPU availability without generation.",
                "Neither inspection spends a correction attempt or approves Canon.",
            ]
        )
        return "\n".join(lines)


def inspect_dual_workflows(
    config: XCICConfiguration,
    *,
    managed_path: Path | None = None,
) -> DualWorkflowInspection:
    """Inspect two distinct graph files; failure in one does not hide the other."""
    legacy = inspect_spatial_guidance(config)
    path = managed_path if managed_path is not None else default_workflow_path()
    try:
        managed = inspect_managed_qwen_edit_workflow(path)
    except (ManagedQwenEditError, OSError, ValueError) as exc:
        return DualWorkflowInspection(
            legacy_path=legacy.workflow_path,
            legacy_description=legacy.describe(),
            managed_path=path,
            managed_source_conditioned=False,
            managed_workflow_sha256=None,
            managed_error=f"{type(exc).__name__}: {exc}",
        )
    return DualWorkflowInspection(
        legacy_path=legacy.workflow_path,
        legacy_description=legacy.describe(),
        managed_path=path,
        managed_source_conditioned=True,
        managed_workflow_sha256=managed.workflow_sha256,
        managed_error=None,
    )
