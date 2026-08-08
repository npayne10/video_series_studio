"""Unit tests for the Phase 18.2.11.2.5a ComfyUI derived-reference provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vscs.application.caps.derived_reference_generation import DerivedReferenceRequest
from vscs.domain.caps import CanonicalReferenceView
from vscs.infrastructure.ai.comfyui_derived_reference_provider import (
    ComfyUIDerivedReferenceConfiguration,
    ComfyUIDerivedReferenceProvider,
)
from vscs.infrastructure.workflows import WorkflowPurpose, default_workflow_registry


class _Client:
    def __init__(self) -> None:
        self.prompt: dict[str, Any] | None = None
        self.validated = False

    def healthcheck(self) -> None:
        return None

    def validate_nodes(self, prompt: dict[str, Any]) -> None:
        self.validated = True

    def submit(self, prompt: dict[str, Any]) -> str:
        self.prompt = prompt
        return "prompt-1"

    def wait(self, prompt_id: str, timeout_seconds: float = 3600.0) -> dict[str, Any]:
        assert prompt_id == "prompt-1"
        assert self.prompt is not None
        queue_path = Path(self.prompt["171"]["inputs"]["queue_file"])
        jobs = json.loads(queue_path.read_text(encoding="utf-8"))
        job = jobs[0]
        destination = Path(job["directory"]) / str(job["filename"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"real-png-candidate")
        return {"status": {"completed": True}}


def test_default_registry_contains_qwen_derived_reference_workflow() -> None:
    registry = default_workflow_registry()
    workflow = registry.require("qwen.derived-reference.v2.1")

    assert workflow.purpose is WorkflowPurpose.DERIVED_REFERENCE
    assert workflow.production_capable is True
    assert workflow.template_path.name == "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
    assert "__VSCS_QUEUE_FILE__" in workflow.load_text()


def test_comfyui_provider_compiles_master_conditioned_runtime_job(tmp_path: Path) -> None:
    project = tmp_path / "Production"
    master = project / "references" / "master.png"
    master.parent.mkdir(parents=True)
    master.write_bytes(b"master")
    client = _Client()
    provider = ComfyUIDerivedReferenceProvider(
        ComfyUIDerivedReferenceConfiguration(base_url="http://127.0.0.1:8188"),
        client=client,  # type: ignore[arg-type]
    )

    generated = provider.generate(
        DerivedReferenceRequest(
            asset_id="CAP-SHP-004",
            title="Guild Tug Ship",
            view=CanonicalReferenceView.TOP,
            master_path=master,
            prompt="Produce the exact same ship from above.",
            negative_prompt="identity drift",
            seed=42,
            project_directory=project,
        )
    )

    assert generated.content == b"real-png-candidate"
    assert generated.media_type == "image/png"
    assert generated.provider_name == "ComfyUI — Qwen Derived Reference v2.1"
    assert client.validated is True
    assert client.prompt is not None
    assert client.prompt["170:169"]["inputs"]["seed"] == 42

    queue_path = Path(client.prompt["171"]["inputs"]["queue_file"])
    job = json.loads(queue_path.read_text(encoding="utf-8"))[0]
    assert Path(job["master_reference"]) == master
    assert job["positive_prompt"] == "Produce the exact same ship from above."
    assert job["negative_prompt"] == "identity drift"
    assert job["view"] == "top"
    assert job["enable_4steps_lora"] is True

    runtime = project / ".vscs" / "runtime" / "comfyui"
    assert tuple((runtime / "compiled").glob("*.json"))
    assert tuple((runtime / "jobs").glob("*/job.json"))
