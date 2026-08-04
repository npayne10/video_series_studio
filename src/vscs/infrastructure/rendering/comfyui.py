"""Manifest-driven ComfyUI adapter foundation without live execution."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from vscs.application.rendering import (
    CompiledRenderRequest,
    RenderAdapter,
    RenderJob,
    RenderJobStatus,
    RendererKind,
    RenderOutput,
    RenderRequest,
    RequestValidation,
    WorkflowCapabilities,
    WorkflowCompatibilityValidator,
    WorkflowInputKind,
    WorkflowManifest,
    WorkflowNodeSelector,
    WorkflowRegistry,
)


class ComfyUIAdapterError(RuntimeError):
    """Raised when a ComfyUI workflow cannot be loaded or compiled."""


class ComfyUIInputResolver(Protocol):
    """Resolve renderer-neutral workflow inputs for one render request."""

    def resolve(self, request: RenderRequest) -> dict[WorkflowInputKind, object]:
        """Return values available for manifest-driven workflow injection."""
        ...


@dataclass(frozen=True, slots=True)
class MetadataComfyUIInputResolver:
    """Temporary resolver using request metadata until Prompt Graph integration."""

    def resolve(self, request: RenderRequest) -> dict[WorkflowInputKind, object]:
        """Resolve technical settings and optional values from request metadata."""
        values: dict[WorkflowInputKind, object] = {
            WorkflowInputKind.WIDTH: request.render.width,
            WorkflowInputKind.HEIGHT: request.render.height,
            WorkflowInputKind.FRAME_COUNT: request.render.frame_count,
            WorkflowInputKind.FRAMES_PER_SECOND: request.render.frames_per_second,
            WorkflowInputKind.OUTPUT_DIRECTORY: request.output.relative_directory,
            WorkflowInputKind.FILENAME_STEM: request.output.filename_stem,
        }
        optional = {
            WorkflowInputKind.POSITIVE_PROMPT: "positive_prompt",
            WorkflowInputKind.NEGATIVE_PROMPT: "negative_prompt",
            WorkflowInputKind.START_FRAME: "start_frame",
            WorkflowInputKind.END_FRAME: "end_frame",
            WorkflowInputKind.REFERENCE_IMAGE: "reference_image",
            WorkflowInputKind.REFERENCE_IMAGES: "reference_images",
            WorkflowInputKind.LORA: "lora",
            WorkflowInputKind.AUDIO: "audio",
        }
        for input_kind, metadata_key in optional.items():
            value = request.metadata.get(metadata_key)
            if value:
                values[input_kind] = value
        if request.render.seed is not None:
            values[WorkflowInputKind.SEED] = request.render.seed
        return values


@dataclass(frozen=True, slots=True)
class ComfyUIWorkflowCompiler:
    """Load API workflows, resolve nodes, and inject manifest-bound values."""

    workflow_root: Path

    def load_workflow(self, manifest: WorkflowManifest) -> dict[str, object]:
        """Load one ComfyUI API workflow declared by a manifest."""
        if manifest.workflow_file is None:
            raise ComfyUIAdapterError(
                "workflow manifest does not declare workflow_file"
            )
        path = (self.workflow_root / manifest.workflow_file).resolve(strict=False)
        root = self.workflow_root.resolve(strict=False)
        if path != root and root not in path.parents:
            raise ComfyUIAdapterError("workflow file must remain inside workflow root")
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ComfyUIAdapterError(f"cannot load ComfyUI workflow: {exc}") from exc
        if not isinstance(raw, dict):
            raise ComfyUIAdapterError("ComfyUI API workflow root must be an object")
        if any(not isinstance(node, dict) for node in raw.values()):
            raise ComfyUIAdapterError("every ComfyUI workflow node must be an object")
        return raw

    def compile(
        self,
        manifest: WorkflowManifest,
        values: dict[WorkflowInputKind, object],
    ) -> dict[str, object]:
        """Return a copied workflow with manifest-declared inputs injected."""
        workflow = copy.deepcopy(self.load_workflow(manifest))
        for binding in manifest.bindings:
            if binding.input_kind not in values:
                if binding.required:
                    raise ComfyUIAdapterError(
                        f"missing required workflow input: {binding.input_kind.value}"
                    )
                continue
            node_id = self._resolve_node_id(workflow, binding.selector)
            self._set_field(
                workflow[node_id],
                binding.field_path,
                values[binding.input_kind],
            )
        return workflow

    @staticmethod
    def _resolve_node_id(
        workflow: dict[str, object],
        selector: WorkflowNodeSelector,
    ) -> str:
        if selector.node_id is not None:
            if selector.node_id not in workflow:
                raise ComfyUIAdapterError(
                    f"workflow node does not exist: {selector.node_id}"
                )
            return selector.node_id

        matches: list[str] = []
        for candidate_id, raw_node in workflow.items():
            node = raw_node if isinstance(raw_node, dict) else {}
            metadata = node.get("_meta", {})
            node_title = metadata.get("title") if isinstance(metadata, dict) else None
            if selector.node_title is not None and node_title != selector.node_title:
                continue
            if (
                selector.class_type is not None
                and node.get("class_type") != selector.class_type
            ):
                continue
            matches.append(candidate_id)
        if not matches:
            raise ComfyUIAdapterError(
                "workflow node selector did not match: "
                f"{selector.logical_name}"
            )
        if len(matches) > 1:
            raise ComfyUIAdapterError(
                "workflow node selector is ambiguous: "
                f"{selector.logical_name}"
            )
        return matches[0]

    @staticmethod
    def _set_field(node: object, field_path: str, value: object) -> None:
        if not isinstance(node, dict):
            raise ComfyUIAdapterError("selected workflow node is not an object")
        parts = tuple(part for part in field_path.split(".") if part)
        if not parts:
            raise ComfyUIAdapterError("workflow field path is empty")
        current: dict[str, object] = node
        for part in parts[:-1]:
            child = current.get(part)
            if child is None:
                child = {}
                current[part] = child
            if not isinstance(child, dict):
                raise ComfyUIAdapterError(
                    f"workflow field path is not writable: {field_path}"
                )
            current = child
        current[parts[-1]] = value


@dataclass(slots=True)
class ComfyUIAdapter(RenderAdapter):
    """Compile ComfyUI payloads while keeping execution in dry-run mode."""

    registry: WorkflowRegistry
    compatibility: WorkflowCompatibilityValidator
    compiler: ComfyUIWorkflowCompiler
    resolver: ComfyUIInputResolver = field(
        default_factory=MetadataComfyUIInputResolver
    )
    renderer: RendererKind = RendererKind.COMFYUI

    def capabilities(self, workflow_id: str) -> WorkflowCapabilities:
        """Return typed capabilities declared by one registered workflow."""
        manifest = self.registry.require(workflow_id)
        return self.compatibility.manifest_capabilities(manifest)

    def validate_request(self, request: RenderRequest) -> RequestValidation:
        """Validate identity, compatibility, workflow file, and required inputs."""
        messages: list[str] = []
        if request.renderer is not self.renderer:
            messages.append("render request does not target ComfyUI")
            return RequestValidation(False, tuple(messages))
        manifest = self.registry.get(request.workflow_id)
        if manifest is None:
            return RequestValidation(
                False,
                (f"workflow manifest is not registered: {request.workflow_id}",),
            )
        report = self.compatibility.validate(request, manifest)
        messages.extend(item.message for item in report.errors)
        try:
            values = self.resolver.resolve(request)
            self.compiler.compile(manifest, values)
        except ComfyUIAdapterError as exc:
            messages.append(str(exc))
        return RequestValidation(not messages, tuple(messages))

    def compile_request(self, request: RenderRequest) -> CompiledRenderRequest:
        """Compile a universal request into a ComfyUI prompt payload."""
        validation = self.validate_request(request)
        if not validation.passed:
            raise ComfyUIAdapterError("; ".join(validation.messages))
        manifest = self.registry.require(request.workflow_id)
        workflow = self.compiler.compile(manifest, self.resolver.resolve(request))
        payload: dict[str, object] = {
            "prompt": workflow,
            "client_id": request.metadata.get("client_id", request.request_id),
            "extra_data": {
                "vscs_request_id": request.request_id,
                "production_id": request.production_id,
                "scene_id": request.scene_id,
                "shot_id": request.shot_id,
                "clip_id": request.clip_id,
                "quality_level": request.quality_level.value,
            },
        }
        return CompiledRenderRequest(
            request_id=request.request_id,
            renderer=self.renderer,
            workflow_id=request.workflow_id,
            payload=payload,
        )

    def submit(self, request: CompiledRenderRequest) -> RenderJob:
        """Create a queued dry-run job without contacting ComfyUI."""
        if request.renderer is not self.renderer:
            raise ComfyUIAdapterError("compiled request does not target ComfyUI")
        return RenderJob(
            job_id=f"DRY-{uuid4().hex}",
            request_id=request.request_id,
            status=RenderJobStatus.QUEUED,
            submitted_at=datetime.now(UTC),
            renderer_job_id=f"dry-run:{request.request_id}",
        )

    def monitor(self, job: RenderJob) -> RenderJob:
        """Return an unchanged dry-run job until live execution is added."""
        return job

    def cancel(self, job: RenderJob) -> RenderJob:
        """Cancel a queued dry-run job."""
        if job.status is RenderJobStatus.CANCELLED:
            return job
        if job.status is not RenderJobStatus.QUEUED:
            raise ComfyUIAdapterError("only queued dry-run jobs can be cancelled")
        return job.transition(
            RenderJobStatus.CANCELLED,
            finished_at=datetime.now(UTC),
        )

    def fetch_outputs(self, job: RenderJob) -> tuple[RenderOutput, ...]:
        """Return no outputs because live execution is intentionally disabled."""
        return job.outputs
