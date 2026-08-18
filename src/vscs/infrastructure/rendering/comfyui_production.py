"""ComfyUI production-package workflow integration for Phase 20.6."""

from __future__ import annotations

import copy
from dataclasses import dataclass

from vscs.application.rendering import CompiledRenderRequest, RenderRequest

from .comfyui import ComfyUIAdapter, ComfyUIAdapterError


@dataclass(slots=True)
class ProductionPackageComfyUIAdapter(ComfyUIAdapter):
    """Compile a ComfyUI workflow and inject the queue-selected production package."""

    production_package_class_type: str = "XorixProductionPackageLoaderV714"
    production_package_title: str = "Xorix Production Package — Canonical Composition v7.1.4"

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        compiled = super().compile_request(request)
        package = request.metadata.get("production_package", "").strip()
        if not package:
            raise ComfyUIAdapterError("production_package metadata is required")
        payload = copy.deepcopy(compiled.payload)
        prompt = payload.get("prompt")
        if not isinstance(prompt, dict):
            raise ComfyUIAdapterError("compiled ComfyUI prompt must be an object")
        matches: list[dict[str, object]] = []
        for raw_node in prompt.values():
            if not isinstance(raw_node, dict):
                continue
            metadata = raw_node.get("_meta", {})
            title = metadata.get("title") if isinstance(metadata, dict) else None
            if raw_node.get("class_type") != self.production_package_class_type:
                continue
            if title != self.production_package_title:
                continue
            matches.append(raw_node)
        if len(matches) != 1:
            raise ComfyUIAdapterError(
                "production package loader must resolve to exactly one semantic workflow node"
            )
        inputs = matches[0].get("inputs")
        if not isinstance(inputs, dict):
            raise ComfyUIAdapterError("production package loader inputs must be an object")
        inputs["production_package"] = package
        return CompiledRenderRequest(
            request_id=compiled.request_id,
            renderer=compiled.renderer,
            workflow_id=compiled.workflow_id,
            payload=payload,
        )
