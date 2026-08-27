"""LTX 2.3 Video Studio provider-edge workflow integration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vscs.application.rendering import RenderRequest, WorkflowInputKind

from .comfyui import (
    ComfyUIAdapter,
    ComfyUIAdapterError,
    ComfyUIWorkflowCompiler,
    MetadataComfyUIInputResolver,
)

LTX23_VIDEO_STUDIO_WORKFLOW_ID = "ltx23_production_v1"
LTX23_VIDEO_STUDIO_DISPLAY_NAME = "LTX-2.3 Video Studio Production"


@dataclass(frozen=True, slots=True)
class LTX23VideoStudioInputResolver(MetadataComfyUIInputResolver):
    """Resolve multi-reference VSCS metadata into typed LTX workflow inputs."""

    def resolve(self, request: RenderRequest) -> dict[WorkflowInputKind, object]:
        values = super().resolve(request)
        raw_references = request.metadata.get("reference_images", "").strip()
        if raw_references:
            try:
                parsed = json.loads(raw_references)
            except json.JSONDecodeError as exc:
                raise ComfyUIAdapterError(
                    "reference_images metadata must be a JSON array for LTX 2.3"
                ) from exc
            if not isinstance(parsed, list) or any(
                not isinstance(item, str) or not item.strip() for item in parsed
            ):
                raise ComfyUIAdapterError(
                    "reference_images metadata must contain non-empty image paths"
                )
            values[WorkflowInputKind.REFERENCE_IMAGES] = [item.strip() for item in parsed]
        return values


@dataclass(frozen=True, slots=True)
class LTX23VideoStudioDeploymentValidator:
    """Verify that the approved Video Studio API workflow is deployable before live execution."""

    workflow_root: Path
    relative_workflow_path: str = "workflows/ltx23_production_v1_api.json"

    def validate(self) -> tuple[str, ...]:
        findings: list[str] = []
        root = self.workflow_root.resolve(strict=False)
        path = (root / self.relative_workflow_path).resolve(strict=False)
        if path != root and root not in path.parents:
            return ("LTX 2.3 workflow path escapes the configured workflow root",)
        if not path.is_file():
            return (f"LTX-2.3 Video Studio Production API workflow is not installed at {path}",)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return (f"LTX 2.3 workflow cannot be read as API JSON: {exc}",)
        if not isinstance(raw, dict) or not raw:
            findings.append("LTX 2.3 API workflow must be a non-empty object")
        return tuple(findings)


def build_ltx23_video_studio_foundation(
    foundation: ComfyUIAdapter,
) -> ComfyUIAdapter:
    """Return a ComfyUI foundation using the governed LTX multi-reference resolver."""
    return ComfyUIAdapter(
        registry=foundation.registry,
        compatibility=foundation.compatibility,
        compiler=ComfyUIWorkflowCompiler(foundation.compiler.workflow_root),
        resolver=LTX23VideoStudioInputResolver(),
    )
