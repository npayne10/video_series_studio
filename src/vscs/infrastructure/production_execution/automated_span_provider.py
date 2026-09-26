"""Live LTX-2.5 provider driver for Phase 20.18.2.3.6 internal spans."""

from __future__ import annotations

import json
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from vscs.application.rendering import (
    AssetPackageReference,
    ContinuityPackageReference,
    OutputSettings,
    PromptPackageReference,
    QualityLevel,
    RendererKind,
    RenderJobStatus,
    RenderOutputKind,
    RenderRequest,
    RenderSettings,
    WorkflowCompatibilityValidator,
    WorkflowManifest,
    WorkflowRegistry,
)
from vscs.infrastructure.rendering import (
    ComfyUIClient,
    ComfyUIWorkflowCompiler,
    LiveComfyUIAdapter,
    ProductionPackageComfyUIAdapter,
    UrllibComfyUITransport,
)

from .ltx25_keyframe_contract import (
    LTX25_KEYFRAME_LOADER_CLASS,
    LTX25_KEYFRAME_LOADER_TITLE,
    LTX25_KEYFRAME_MANIFEST_FILE,
    LTX25_KEYFRAME_WORKFLOW_ID,
)


class AutomatedSpanProviderError(RuntimeError):
    """Raised when an internal span cannot complete through the live provider."""


class LTX25AutomatedSpanProvider:
    """Execute one isolated governed span without creating another ProductionTask attempt."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_output_directory: Path,
        timeout_seconds: float = 3600.0,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.endpoint = endpoint.strip().rstrip("/")
        self.comfyui_output_directory = (
            Path(comfyui_output_directory).expanduser().resolve(strict=False)
        )
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        if not self.endpoint:
            raise AutomatedSpanProviderError("Automated span execution requires a ComfyUI endpoint")
        if not self.comfyui_output_directory.is_dir():
            raise AutomatedSpanProviderError(
                "Automated span execution requires the configured ComfyUI output directory"
            )

    def render(self, package_path: Path) -> Path:
        package = self._read_package(package_path)
        adapter = self._adapter()
        request = self._request(package_path, package)
        try:
            compiled = adapter.compile_request(request)
            job = adapter.submit(compiled)
            started = time.monotonic()
            while time.monotonic() - started <= self.timeout_seconds:
                job = adapter.monitor(job)
                if job.status is RenderJobStatus.COMPLETED:
                    outputs = adapter.fetch_outputs(job)
                    video = next(
                        (
                            item
                            for item in outputs
                            if item.kind is RenderOutputKind.PRODUCTION_VIDEO
                        ),
                        None,
                    )
                    if video is None:
                        raise AutomatedSpanProviderError(
                            "LTX-2.5 completed without a production-video output"
                        )
                    resolved = (self.comfyui_output_directory / video.relative_path).resolve(
                        strict=False
                    )
                    if not resolved.is_relative_to(self.comfyui_output_directory):
                        raise AutomatedSpanProviderError(
                            "Provider output escaped the configured ComfyUI output directory"
                        )
                    if not resolved.is_file():
                        raise AutomatedSpanProviderError(
                            f"Provider output does not exist: {resolved}"
                        )
                    return resolved
                if job.status is RenderJobStatus.FAILED:
                    raise AutomatedSpanProviderError(
                        job.failure_reason or "LTX-2.5 internal span execution failed"
                    )
                time.sleep(self.poll_interval_seconds)
        finally:
            with suppress(Exception):
                adapter.free_models_and_memory()
        raise AutomatedSpanProviderError(
            f"LTX-2.5 internal span render timed out after {self.timeout_seconds:.0f} seconds"
        )

    def free_models_and_memory(self) -> None:
        self._adapter().free_models_and_memory()

    def _adapter(self) -> LiveComfyUIAdapter:
        repository_root = Path(__file__).resolve().parents[4]
        workflow_root = repository_root / "resources" / "workflows"
        manifest_path = workflow_root / "manifests" / LTX25_KEYFRAME_MANIFEST_FILE
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedSpanProviderError(
                f"Cannot load LTX-2.5 Candidate C workflow manifest: {exc}"
            ) from exc
        registry = WorkflowRegistry()
        registry.register(WorkflowManifest.from_dict(raw))
        foundation = ProductionPackageComfyUIAdapter(
            registry,
            WorkflowCompatibilityValidator(),
            ComfyUIWorkflowCompiler(workflow_root),
            production_package_class_type=LTX25_KEYFRAME_LOADER_CLASS,
            production_package_title=LTX25_KEYFRAME_LOADER_TITLE,
            submission_audit_directory=(
                self.project_directory / ".vscs" / "provider_executions" / "payload_audit"
            ),
        )
        transport = UrllibComfyUITransport(self.endpoint, timeout_seconds=15.0)
        return LiveComfyUIAdapter(
            foundation=foundation,
            client=ComfyUIClient(transport, self.endpoint),
        )

    def _request(self, package_path: Path, package: dict[str, Any]) -> RenderRequest:
        manifest = package.get("_vscs_manifest")
        if not isinstance(manifest, dict):
            raise AutomatedSpanProviderError("Internal span package has no VSCS manifest")
        execution = package.get("timed_span_execution")
        if not isinstance(execution, dict):
            raise AutomatedSpanProviderError(
                "Internal span package has no span execution authority"
            )
        task_id = str(manifest.get("task_id") or "").strip()
        shot_id = str(manifest.get("shot_id") or "").strip()
        scene_id = str(manifest.get("scene_id") or "").strip()
        episode_id = str(manifest.get("episode_id") or "").strip()
        production_id = str(manifest.get("production_id") or "").strip()
        span_id = str(execution.get("span_id") or "").strip()
        sequence = int(execution.get("sequence_number") or 0)
        if not all((task_id, shot_id, scene_id, episode_id, production_id, span_id, sequence)):
            raise AutomatedSpanProviderError("Internal span package identity is incomplete")
        width = int(package.get("width") or 0)
        height = int(package.get("height") or 0)
        fps = int(package.get("fps") or 0)
        frames = int(package.get("frame_count") or 0)
        seed = int(package.get("seed") or 0)
        authority_id = str(manifest.get("authority_id") or "AUTOMATED-SPAN")
        return RenderRequest(
            request_id=f"REQ-AUTO-{task_id}-SPAN-{sequence:03d}",
            production_id=production_id,
            container_id=episode_id,
            scene_id=scene_id,
            shot_id=shot_id,
            clip_id=span_id,
            renderer=RendererKind.COMFYUI,
            workflow_id=LTX25_KEYFRAME_WORKFLOW_ID,
            quality_level=QualityLevel.PRODUCTION,
            prompt_package=PromptPackageReference(authority_id),
            assets=AssetPackageReference(),
            continuity=ContinuityPackageReference(),
            render=RenderSettings(
                width=width,
                height=height,
                frames_per_second=fps,
                frame_count=frames,
                seed=seed,
            ),
            output=OutputSettings(
                relative_directory="vscs-automated-spans",
                filename_stem=f"{task_id}-span-{sequence:03d}",
            ),
            metadata={"production_package": str(Path(package_path).resolve(strict=False))},
        )

    @staticmethod
    def _read_package(path: Path) -> dict[str, Any]:
        candidate = Path(path).expanduser().resolve(strict=False)
        try:
            raw = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedSpanProviderError(f"Cannot read internal span package: {exc}") from exc
        if not isinstance(raw, dict):
            raise AutomatedSpanProviderError("Internal span package root must be an object")
        return raw
