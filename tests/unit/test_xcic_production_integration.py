"""Tests for Phase 15.2 XCIC Core production integration."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from vscs.application.acpp import (
    RenderCapability,
    RenderInputReference,
    RenderJob,
    RenderQualityMode,
    RetryPolicy,
    SeedPolicy,
)
from vscs.application.production_pipeline import (
    ExecutionLease,
    ExecutionRequest,
    WorkerIdentity,
)
from vscs.infrastructure.production import (
    ComfyUIClient,
    ComfyUIExecutorConfig,
    ComfyUIProductionExecutor,
    XCICCoreWorkflowCompiler,
    XCICWorkflowCompilationError,
)
from vscs.infrastructure.xcic_core.models import XCICCoreWorkflow


class MappingReferenceResolver:
    def __init__(self, values: dict[str, Path]) -> None:
        self.values = values

    def resolve(self, reference_id: str) -> Path:
        return self.values[reference_id]


class SuccessfulClient(ComfyUIClient):
    def __init__(self) -> None:
        super().__init__(
            ComfyUIExecutorConfig(require_outputs=True),
            sleeper=lambda _seconds: None,
        )
        self.submitted: dict[str, Any] | None = None

    def healthcheck(self) -> None:
        pass

    def submit(self, workflow: dict[str, Any]) -> str:
        self.submitted = workflow
        return "prompt-xcic"

    def wait(self, prompt_id: str) -> dict[str, Any]:
        assert prompt_id == "prompt-xcic"
        return {
            "outputs": {
                "9": {
                    "videos": [
                        {"filename": "clip-001.mp4", "subfolder": "production"}
                    ]
                }
            }
        }


def _workflow(tmp_path: Path, *, loaders: int = 1) -> XCICCoreWorkflow:
    nodes: dict[str, Any] = {
        "2": {"class_type": "Sampler", "inputs": {"value": 1}},
    }
    for index in range(loaders):
        nodes[str(index + 10)] = {
            "class_type": "VSCSXCICQueueLoader",
            "inputs": {"queue_file": "", "job_index": 99, "quality_mode": ""},
        }
    editable = tmp_path / "xcic_workflow.json"
    editable.write_text(json.dumps(nodes), encoding="utf-8")
    return XCICCoreWorkflow(
        workflow_id="xcic-video",
        editable_path=editable,
        compiled_path=tmp_path / "compiled.json",
        loader_class="VSCSXCICQueueLoader",
        queue_file_path=tmp_path / "queue.json",
        version="2.0",
    )


def _job(
    *,
    seed_policy: SeedPolicy = SeedPolicy.FIXED,
    fixed_seed: int | None = 42,
    references: tuple[RenderInputReference, ...] = (),
    start_reference_id: str | None = None,
    metadata: tuple[tuple[str, str], ...] = (),
) -> RenderJob:
    return RenderJob(
        job_id="JOB-001",
        clip_id="CLIP-001",
        width=1920,
        height=800,
        frames_per_second=24,
        frame_count=240,
        quality_mode=RenderQualityMode.PRODUCTION,
        seed_policy=seed_policy,
        fixed_seed=fixed_seed,
        positive_prompt="James stands on the bridge.",
        negative_prompt="No identity drift.",
        input_references=references,
        start_reference_id=start_reference_id,
        end_reference_id=None,
        output_path="production/clip-001.mp4",
        dependencies=(),
        retry_policy=RetryPolicy(),
        required_capabilities=(RenderCapability.TEXT_TO_VIDEO,),
        package_checksum="package-checksum",
        prompt_checksum="prompt-checksum",
        metadata=metadata,
    )


def test_compiler_writes_queue_and_patches_loader(tmp_path: Path) -> None:
    workflow = _workflow(tmp_path)
    compiler = XCICCoreWorkflowCompiler(workflow)

    prompt = compiler.compile(_job(metadata=(("xcic.steps", "8"), ("xcic.cfg", "1.5"))))

    loader_inputs = prompt["10"]["inputs"]
    assert loader_inputs["queue_file"] == str(workflow.queue_file_path.resolve())
    assert loader_inputs["job_index"] == 0
    assert loader_inputs["quality_mode"] == "production"
    payload = json.loads(workflow.queue_file_path.read_text(encoding="utf-8"))
    queued = payload["jobs"][0]
    assert queued["job_id"] == "JOB-001"
    assert queued["asset_id"] == "CLIP-001"
    assert queued["seed"] == 42
    assert queued["steps"] == 8
    assert queued["cfg"] == 1.5
    assert queued["candidate_filename"] == "clip-001.mp4"
    assert queued["metadata"]["workflow_version"] == "2.0"


def test_compiler_resolves_primary_reference(tmp_path: Path) -> None:
    reference = tmp_path / "james.png"
    reference.write_bytes(b"reference")
    compiler = XCICCoreWorkflowCompiler(
        _workflow(tmp_path),
        reference_resolver=MappingReferenceResolver({"REF-JAMES": reference}),
    )

    compiler.compile(
        _job(
            references=(RenderInputReference("REF-JAMES", "canonical"),),
            start_reference_id="REF-JAMES",
        )
    )

    payload = json.loads((tmp_path / "queue.json").read_text(encoding="utf-8"))
    assert payload["jobs"][0]["reference_path"] == str(reference)
    assert payload["jobs"][0]["identity_reference"] == str(reference)


def test_compiler_requires_resolver_for_reference_jobs(tmp_path: Path) -> None:
    compiler = XCICCoreWorkflowCompiler(_workflow(tmp_path))

    with pytest.raises(XCICWorkflowCompilationError, match="reference resolver"):
        compiler.compile(
            _job(references=(RenderInputReference("REF-JAMES", "canonical"),))
        )


def test_derived_seed_is_stable_and_random_seed_uses_sentinel(tmp_path: Path) -> None:
    workflow = _workflow(tmp_path)
    compiler = XCICCoreWorkflowCompiler(workflow)
    derived = _job(seed_policy=SeedPolicy.DERIVED, fixed_seed=None)

    compiler.compile(derived)
    first = json.loads(workflow.queue_file_path.read_text(encoding="utf-8"))["jobs"][0][
        "seed"
    ]
    compiler.compile(derived)
    second = json.loads(workflow.queue_file_path.read_text(encoding="utf-8"))["jobs"][0][
        "seed"
    ]
    compiler.compile(_job(seed_policy=SeedPolicy.RANDOM, fixed_seed=None))
    random_seed = json.loads(workflow.queue_file_path.read_text(encoding="utf-8"))[
        "jobs"
    ][0]["seed"]

    assert first == second
    assert first >= 0
    assert random_seed == -1


def test_compiler_rejects_missing_or_duplicate_loader(tmp_path: Path) -> None:
    with pytest.raises(XCICWorkflowCompilationError, match="exactly one"):
        XCICCoreWorkflowCompiler(_workflow(tmp_path, loaders=0)).compile(_job())
    with pytest.raises(XCICWorkflowCompilationError, match="exactly one"):
        XCICCoreWorkflowCompiler(_workflow(tmp_path, loaders=2)).compile(_job())


def test_xcic_compiler_executes_through_comfyui_executor(tmp_path: Path) -> None:
    compiler = XCICCoreWorkflowCompiler(_workflow(tmp_path))
    client = SuccessfulClient()
    executor = ComfyUIProductionExecutor(compiler, client)
    now = datetime.now(UTC)
    worker = WorkerIdentity(
        worker_id="worker-xcic",
        executor_id="comfyui",
        capabilities=frozenset(RenderCapability),
    )
    request = ExecutionRequest(
        job=_job(),
        worker=worker,
        lease=ExecutionLease(
            lease_id="LEASE-XCIC",
            worker_id=worker.worker_id,
            job_id="JOB-001",
            acquired_at=now,
            expires_at=now + timedelta(minutes=10),
            last_heartbeat_at=now,
        ),
        submitted_at=now,
    )

    result = executor.execute(request)

    assert result.succeeded is True
    assert result.output_paths == ("production/clip-001.mp4",)
    assert client.submitted is not None
    assert client.submitted["10"]["inputs"]["job_index"] == 0
