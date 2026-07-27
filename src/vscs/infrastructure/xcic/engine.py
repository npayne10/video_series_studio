"""Queue-based XCIC rendering engine backed by ComfyUI."""

from __future__ import annotations

import time
from pathlib import Path

from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.xcic.comfyui import ComfyUIClient, ComfyUIError
from vscs.infrastructure.xcic.models import (
    XCICGenerationJob,
    XCICRenderedFile,
    XCICWorkflowDefinition,
)
from vscs.infrastructure.xcic.queue import XCICQueueWriter


class XCICRenderingError(RuntimeError):
    """Raised when an XCIC render cannot be queued or collected."""


class XCICRenderingEngine:
    """Write XCIC jobs, run a ComfyUI workflow, and collect generated files."""

    def __init__(
        self,
        workflow: XCICWorkflowDefinition,
        client: ComfyUIClient | None = None,
        queue_writer: XCICQueueWriter | None = None,
    ) -> None:
        self.workflow = workflow
        self.client = client or ComfyUIClient()
        self.queue_writer = queue_writer or XCICQueueWriter()
        self._logger = LoggingService.get_logger("xcic.engine")

    def render(
        self,
        jobs: tuple[XCICGenerationJob, ...],
        timeout_seconds: float = 900.0,
    ) -> tuple[XCICRenderedFile, ...]:
        self.queue_writer.write(self.workflow.queue_file_path, jobs)
        for job in jobs:
            job.candidate_directory.mkdir(parents=True, exist_ok=True)
        try:
            self.client.healthcheck()
            prompt_id = self.client.submit_workflow(self.workflow.api_workflow_path)
            self.client.wait_for_completion(prompt_id, timeout_seconds)
        except ComfyUIError as exc:
            raise XCICRenderingError(str(exc)) from exc

        deadline = time.monotonic() + min(timeout_seconds, 120.0)
        pending = {job.candidate_directory / job.candidate_filename: job for job in jobs}
        while pending and time.monotonic() < deadline:
            completed = [path for path in pending if path.is_file() and path.stat().st_size > 0]
            for path in completed:
                pending.pop(path)
            if pending:
                time.sleep(0.5)
        if pending:
            missing = ", ".join(str(path) for path in pending)
            raise XCICRenderingError(f"ComfyUI completed but XCIC output files were not found: {missing}")

        outputs = tuple(
            XCICRenderedFile(
                path=job.candidate_directory / job.candidate_filename,
                job=job,
                workflow_name=self.workflow.name,
                workflow_version=self.workflow.version,
            )
            for job in jobs
        )
        self._logger.info("XCIC rendered %s file(s) using %s", len(outputs), self.workflow.name)
        return outputs
