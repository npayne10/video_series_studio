"""Mapped API-workflow XCIC rendering engine backed by ComfyUI."""

from __future__ import annotations

import time

from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.xcic.comfyui import ComfyUIClient, ComfyUIError
from vscs.infrastructure.xcic.models import (
    XCICGenerationJob,
    XCICRenderedFile,
    XCICWorkflowDefinition,
)
from vscs.infrastructure.xcic.workflow import XCICWorkflowError, XCICWorkflowPatcher


class XCICRenderingError(RuntimeError):
    """Raised when an XCIC render cannot be submitted or collected."""


class XCICRenderingEngine:
    """Patch, submit, monitor, and collect independent XCIC generation jobs."""

    def __init__(
        self,
        workflow: XCICWorkflowDefinition,
        client: ComfyUIClient | None = None,
    ) -> None:
        self.workflow = workflow
        self.client = client or ComfyUIClient()
        self.patcher = XCICWorkflowPatcher(
            workflow.api_workflow_path,
            workflow.mapping_path,
            workflow.profile_path,
        )
        self._logger = LoggingService.get_logger("xcic.engine")

    def render(
        self,
        jobs: tuple[XCICGenerationJob, ...],
        timeout_seconds: float = 900.0,
    ) -> tuple[XCICRenderedFile, ...]:
        outputs: list[XCICRenderedFile] = []
        try:
            self.client.healthcheck()
            for job in jobs:
                job.candidate_directory.mkdir(parents=True, exist_ok=True)
                expected = job.candidate_directory / job.candidate_filename
                if expected.exists():
                    expected.unlink()
                workflow = self.patcher.build(job)
                prompt_id = self.client.submit_workflow(workflow)
                self.client.wait_for_completion(prompt_id, timeout_seconds)
                self._wait_for_file(expected, timeout_seconds)
                outputs.append(
                    XCICRenderedFile(
                        path=expected,
                        job=job,
                        workflow_name=self.workflow.name,
                        workflow_version=self.workflow.version,
                    )
                )
        except (ComfyUIError, XCICWorkflowError, OSError) as exc:
            raise XCICRenderingError(str(exc)) from exc

        self._logger.info("XCIC rendered %s file(s) using %s", len(outputs), self.workflow.name)
        return tuple(outputs)

    @staticmethod
    def _wait_for_file(path, timeout_seconds: float) -> None:
        deadline = time.monotonic() + min(timeout_seconds, 120.0)
        while time.monotonic() < deadline:
            if path.is_file() and path.stat().st_size > 0:
                return
            time.sleep(0.5)
        raise XCICRenderingError(f"ComfyUI completed but XCIC output file was not found: {path}")
