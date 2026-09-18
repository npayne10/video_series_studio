"""ComfyUI production-package workflow integration for governed execution."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.rendering import CompiledRenderRequest, RenderRequest

from .comfyui import ComfyUIAdapter, ComfyUIAdapterError


@dataclass(slots=True)
class ProductionPackageComfyUIAdapter(ComfyUIAdapter):
    """Compile a ComfyUI workflow and inject the queue-selected production package."""

    production_package_class_type: str = "XorixProductionPackageLoaderV714"
    production_package_title: str = "Xorix Production Package — Canonical Composition v7.1.4"
    submission_audit_directory: Path | None = None

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        compiled = ComfyUIAdapter.compile_request(self, request)
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
        self._persist_submission_audit(request, payload, package)
        return CompiledRenderRequest(
            request_id=compiled.request_id,
            renderer=compiled.renderer,
            workflow_id=compiled.workflow_id,
            payload=payload,
        )

    def _persist_submission_audit(
        self,
        request: RenderRequest,
        payload: dict[str, object],
        package: str,
    ) -> None:
        """Persist the exact payload that LiveComfyUIAdapter will submit unchanged."""
        if self.submission_audit_directory is None:
            return
        package_path = Path(package).expanduser().resolve(strict=False)
        if not package_path.is_file():
            raise ComfyUIAdapterError(
                f"production package does not exist for provider payload audit: {package_path}"
            )
        try:
            package_raw = json.loads(package_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ComfyUIAdapterError(
                f"production package cannot be audited before provider submission: {exc}"
            ) from exc
        if not isinstance(package_raw, dict):
            raise ComfyUIAdapterError("production package audit source must be a JSON object")

        prompt = payload.get("prompt")
        if not isinstance(prompt, dict):
            raise ComfyUIAdapterError("provider payload audit requires a ComfyUI prompt object")
        workflow_json = self._canonical_json(prompt)
        payload_json = self._canonical_json(payload)

        manifest = package_raw.get("_vscs_manifest")
        manifest_view = manifest if isinstance(manifest, dict) else {}
        reference_plan = package_raw.get("reference_plan")
        reference_view = reference_plan if isinstance(reference_plan, dict) else {}
        multi = reference_view.get("provider_multi_reference")
        multi_view = copy.deepcopy(multi) if isinstance(multi, dict) else None

        guide_nodes: list[dict[str, Any]] = []
        for node_id, raw_node in sorted(prompt.items(), key=lambda item: str(item[0])):
            if not isinstance(raw_node, dict):
                continue
            if raw_node.get("class_type") != "LTXAddVideoICLoRAGuide":
                continue
            inputs = raw_node.get("inputs")
            if not isinstance(inputs, dict):
                continue
            metadata = raw_node.get("_meta")
            title = metadata.get("title") if isinstance(metadata, dict) else ""
            guide_nodes.append(
                {
                    "node_id": str(node_id),
                    "title": str(title or ""),
                    "frame_idx": inputs.get("frame_idx"),
                    "image_binding": copy.deepcopy(inputs.get("image")),
                    "strength_binding": copy.deepcopy(inputs.get("strength")),
                }
            )

        audit = {
            "schema_version": "1.0",
            "observed_at": datetime.now(UTC).isoformat(),
            "request": {
                "request_id": request.request_id,
                "production_id": request.production_id,
                "scene_id": request.scene_id,
                "shot_id": request.shot_id,
                "clip_id": request.clip_id,
                "workflow_id": request.workflow_id,
                "quality_level": request.quality_level.value,
            },
            "production_package": {
                "path": str(package_path),
                "package_fingerprint": str(manifest_view.get("package_fingerprint") or ""),
                "authority_fingerprint": str(manifest_view.get("authority_fingerprint") or ""),
                "source_package_id": str(manifest_view.get("source_package_id") or ""),
            },
            "provider_prompt": {
                "positive": str(
                    package_raw.get("positive_prompt")
                    or package_raw.get("shot_prompt")
                    or ""
                ),
                "negative": str(package_raw.get("negative_prompt") or ""),
                "contract": copy.deepcopy(package_raw.get("provider_prompt_contract")),
            },
            "render": {
                "width": package_raw.get("width"),
                "height": package_raw.get("height"),
                "frame_count": package_raw.get("frame_count"),
                "fps": package_raw.get("fps"),
                "seed": package_raw.get("seed"),
            },
            "reference_contract": multi_view,
            "workflow": {
                "sha256": hashlib.sha256(workflow_json.encode("utf-8")).hexdigest(),
                "guide_nodes": guide_nodes,
            },
            "api_payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
            "api_payload": copy.deepcopy(payload),
        }

        directory = self.submission_audit_directory.expanduser().resolve(strict=False)
        directory.mkdir(parents=True, exist_ok=True)
        safe_request = re.sub(r"[^A-Za-z0-9._-]+", "-", request.request_id).strip("-") or "request"
        package_fingerprint = str(manifest_view.get("package_fingerprint") or "unfingerprinted")
        destination = directory / f"{safe_request}-{package_fingerprint[:12]}.json"
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(audit, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temporary.replace(destination)
        except OSError as exc:
            raise ComfyUIAdapterError(
                f"provider payload audit could not be persisted: {exc}"
            ) from exc

    @staticmethod
    def _canonical_json(value: object) -> str:
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
