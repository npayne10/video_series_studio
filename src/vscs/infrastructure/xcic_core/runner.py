"""Queue-loader based XCIC Core Rendering Library v1.0."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from vscs.infrastructure.logging import LoggingService
from vscs.infrastructure.xcic_core.client import XCICCoreClient, XCICCoreClientError
from vscs.infrastructure.xcic_core.compiler import XCICCoreCompileError, compile_workflow
from vscs.infrastructure.xcic_core.models import XCICCoreJob, XCICCoreResult, XCICCoreWorkflow
from vscs.infrastructure.xcic_core.queue import XCICCoreQueueError, XCICCoreQueueWriter


class XCICCoreRenderingError(RuntimeError):
    """Raised when the XCIC Core pipeline cannot complete a render."""


class XCICCoreRenderer:
    """Compile once, patch only the XCIC loader, render, and verify outputs."""

    def __init__(
        self,
        workflow: XCICCoreWorkflow,
        client: XCICCoreClient | None = None,
        queue_writer: XCICCoreQueueWriter | None = None,
    ) -> None:
        self.workflow = workflow
        self.client = client or XCICCoreClient()
        self.queue_writer = queue_writer or XCICCoreQueueWriter()
        self._logger = LoggingService.get_logger("xcic_core.renderer")

    def render(
        self,
        jobs: tuple[XCICCoreJob, ...],
        timeout_seconds: float = 3600.0,
    ) -> tuple[XCICCoreResult, ...]:
        if not jobs:
            return ()
        try:
            template = self._compile()
            self.client.healthcheck()
            self.client.validate_nodes(template)
            self.queue_writer.write(self.workflow.queue_file_path, jobs)
            loader_id = self._loader_id(template)
            results: list[XCICCoreResult] = []
            for index, job in enumerate(jobs):
                job.candidate_directory.mkdir(parents=True, exist_ok=True)
                expected = job.candidate_directory / job.candidate_filename
                self._remove_prior_outputs(expected)
                prompt = copy.deepcopy(template)
                loader_inputs = prompt[loader_id].setdefault("inputs", {})
                loader_inputs["queue_file"] = str(self.workflow.queue_file_path.resolve())
                loader_inputs["job_index"] = index
                if "quality_mode" in loader_inputs or job.quality_mode:
                    loader_inputs["quality_mode"] = job.quality_mode or self.workflow.quality_mode
                prompt_id = self.client.submit(prompt)
                history = self.client.wait(prompt_id, timeout_seconds)
                output = self._wait_for_output(expected, timeout_seconds)
                results.append(
                    XCICCoreResult(
                        job=job,
                        output_path=output,
                        prompt_id=prompt_id,
                        workflow_id=self.workflow.workflow_id,
                        workflow_version=self.workflow.version,
                        history=history,
                    )
                )
            self._logger.info(
                "XCIC Core rendered %s job(s) using %s", len(results), self.workflow.workflow_id
            )
            return tuple(results)
        except (
            XCICCoreClientError,
            XCICCoreCompileError,
            XCICCoreQueueError,
            OSError,
            ValueError,
        ) as exc:
            raise XCICCoreRenderingError(str(exc)) from exc

    def _compile(self) -> dict[str, object]:
        if not self.workflow.editable_path.is_file() and self.workflow.compiled_path.is_file():
            value = json.loads(self.workflow.compiled_path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise XCICCoreCompileError("Compiled XCIC workflow must be a JSON object")
            return value
        api, _removed = compile_workflow(
            self.workflow.editable_path,
            self.workflow.compiled_path,
        )
        return api

    def _loader_id(self, prompt: dict[str, object]) -> str:
        matches = [
            node_id
            for node_id, node in prompt.items()
            if isinstance(node, dict) and node.get("class_type") == self.workflow.loader_class
        ]
        if len(matches) != 1:
            raise XCICCoreRenderingError(
                f"Expected exactly one {self.workflow.loader_class} node, found {len(matches)}"
            )
        return matches[0]

    @staticmethod
    def _remove_prior_outputs(expected: Path) -> None:
        stem = expected.stem
        for path in expected.parent.glob(f"{stem}*.png"):
            if path.is_file():
                path.unlink()

    @staticmethod
    def _wait_for_output(expected: Path, timeout_seconds: float) -> Path:
        deadline = time.monotonic() + min(timeout_seconds, 180.0)
        while time.monotonic() < deadline:
            if expected.is_file() and expected.stat().st_size > 0:
                return expected
            candidates = sorted(expected.parent.glob(f"{expected.stem}*.png"))
            candidates = [path for path in candidates if path.is_file() and path.stat().st_size > 0]
            if candidates:
                return candidates[-1]
            time.sleep(0.5)
        raise XCICCoreRenderingError(
            f"Generation completed but expected XCIC candidate was not found: {expected}"
        )
