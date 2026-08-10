"""XCIC Core workflow compiler for the ComfyUI production executor."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from vscs.application.acpp import RenderJob, SeedPolicy
from vscs.infrastructure.xcic_core.compiler import XCICCoreCompileError, compile_workflow
from vscs.infrastructure.xcic_core.models import XCICCoreJob, XCICCoreWorkflow
from vscs.infrastructure.xcic_core.queue import XCICCoreQueueError, XCICCoreQueueWriter


class XCICReferenceResolver(Protocol):
    """Resolve one canonical or continuity reference ID to a local path."""

    def resolve(self, reference_id: str) -> Path:
        """Return the local file path for one reference identity."""
        ...


class XCICWorkflowCompilationError(RuntimeError):
    """Raised when a render job cannot become an XCIC ComfyUI workflow."""


@dataclass(frozen=True, slots=True)
class XCICWorkflowCompilerConfig:
    """Policy controlling RenderJob-to-XCIC compilation."""

    default_steps: int = 4
    default_cfg: float = 1.0
    queue_job_index: int = 0

    def __post_init__(self) -> None:
        if self.default_steps < 1:
            raise ValueError("default_steps must be at least 1")
        if self.default_cfg <= 0:
            raise ValueError("default_cfg must be positive")
        if self.queue_job_index < 0:
            raise ValueError("queue_job_index must not be negative")


class XCICCoreWorkflowCompiler:
    """Compile renderer-neutral jobs through the XCIC loader workflow contract."""

    def __init__(
        self,
        workflow: XCICCoreWorkflow,
        *,
        reference_resolver: XCICReferenceResolver | None = None,
        queue_writer: XCICCoreQueueWriter | None = None,
        config: XCICWorkflowCompilerConfig | None = None,
    ) -> None:
        self.workflow = workflow
        self.reference_resolver = reference_resolver
        self.queue_writer = queue_writer or XCICCoreQueueWriter()
        self.config = config or XCICWorkflowCompilerConfig()

    def compile(self, job: RenderJob) -> dict[str, Any]:
        """Compile one render job and persist its XCIC loader queue entry."""
        try:
            template, _removed = compile_workflow(
                self.workflow.editable_path,
                self.workflow.compiled_path,
            )
            loader_id = self._loader_id(template)
            xcic_job = self._xcic_job(job)
            self.queue_writer.write(self.workflow.queue_file_path, (xcic_job,))
            prompt = copy.deepcopy(template)
            loader_node = cast(dict[str, Any], prompt[loader_id])
            inputs = cast(dict[str, Any], loader_node.setdefault("inputs", {}))
            inputs["queue_file"] = str(self.workflow.queue_file_path.resolve())
            inputs["job_index"] = self.config.queue_job_index
            inputs["quality_mode"] = xcic_job.quality_mode
            return prompt
        except (
            XCICCoreCompileError,
            XCICCoreQueueError,
            LookupError,
            OSError,
            ValueError,
        ) as exc:
            raise XCICWorkflowCompilationError(str(exc)) from exc

    def _xcic_job(self, job: RenderJob) -> XCICCoreJob:
        output = Path(job.output_path)
        candidate_directory = output.parent if str(output.parent) != "." else Path()
        reference_path = self._primary_reference(job)
        metadata: dict[str, Any] = dict(job.metadata)
        metadata.update(
            {
                "clip_id": job.clip_id,
                "frames_per_second": job.frames_per_second,
                "frame_count": job.frame_count,
                "package_checksum": job.package_checksum,
                "prompt_checksum": job.prompt_checksum,
                "workflow_id": self.workflow.workflow_id,
                "workflow_version": self.workflow.version,
                "reference_ids": [item.reference_id for item in job.input_references],
                "reference_roles": [item.role for item in job.input_references],
            }
        )
        return XCICCoreJob(
            job_id=job.job_id,
            asset_id=job.clip_id,
            positive_prompt=job.positive_prompt,
            negative_prompt=job.negative_prompt,
            candidate_directory=candidate_directory,
            candidate_filename=output.name,
            width=job.width,
            height=job.height,
            seed=self._seed(job),
            steps=self._metadata_int(job, "xcic.steps", self.config.default_steps),
            cfg=self._metadata_float(job, "xcic.cfg", self.config.default_cfg),
            quality_mode=job.quality_mode.value,
            reference_path=reference_path,
            metadata=metadata,
        )

    def _primary_reference(self, job: RenderJob) -> Path | None:
        reference_id = job.start_reference_id
        if reference_id is None and job.input_references:
            reference_id = job.input_references[0].reference_id
        if reference_id is None:
            return None
        if self.reference_resolver is None:
            raise XCICWorkflowCompilationError(
                f"No XCIC reference resolver configured for {reference_id}"
            )
        path = self.reference_resolver.resolve(reference_id)
        if not path.is_file():
            raise XCICWorkflowCompilationError(f"Resolved XCIC reference does not exist: {path}")
        return path

    def _loader_id(self, prompt: dict[str, Any]) -> str:
        matches = [
            node_id
            for node_id, node in prompt.items()
            if isinstance(node, dict) and node.get("class_type") == self.workflow.loader_class
        ]
        if len(matches) != 1:
            raise XCICWorkflowCompilationError(
                f"Expected exactly one {self.workflow.loader_class} node, found {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _seed(job: RenderJob) -> int:
        if job.seed_policy is SeedPolicy.FIXED:
            if job.fixed_seed is None:
                raise XCICWorkflowCompilationError("Fixed seed policy requires fixed_seed")
            return job.fixed_seed
        if job.seed_policy is SeedPolicy.DERIVED:
            digest = hashlib.sha256(
                f"{job.job_id}|{job.package_checksum}|{job.prompt_checksum}".encode()
            ).digest()
            return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF
        return -1

    @staticmethod
    def _metadata_int(job: RenderJob, key: str, default: int) -> int:
        values = dict(job.metadata)
        raw = values.get(key)
        return default if raw is None else int(raw)

    @staticmethod
    def _metadata_float(job: RenderJob, key: str, default: float) -> float:
        values = dict(job.metadata)
        raw = values.get(key)
        return default if raw is None else float(raw)
