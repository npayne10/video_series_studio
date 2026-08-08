"""Production ComfyUI provider for MASTER-conditioned derived references."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceRequest,
    GeneratedDerivedReference,
)
from vscs.infrastructure.workflows import ManagedWorkflowRegistry, default_workflow_registry
from vscs.infrastructure.xcic_core import XCICCoreClient, XCICCoreClientError


class ComfyUIDerivedReferenceError(RuntimeError):
    """Raised when a real ComfyUI derived-reference render cannot complete."""


@dataclass(frozen=True, slots=True)
class ComfyUIDerivedReferenceConfiguration:
    """Runtime configuration for the Qwen Image Edit derived-reference provider."""

    base_url: str = "http://127.0.0.1:8188"
    workflow_id: str = "qwen.derived-reference.v2.1"
    timeout_seconds: float = 3600.0
    quality_mode: str = "standard"
    enable_lightning_lora: bool = True

    @classmethod
    def from_environment(cls) -> ComfyUIDerivedReferenceConfiguration:
        """Load optional ComfyUI endpoint overrides without adding another settings migration."""
        return cls(base_url=os.environ.get("VSCS_COMFYUI_URL", "http://127.0.0.1:8188"))


class ComfyUIDerivedReferenceProvider:
    """Run the VSCS Qwen Image Edit workflow against a locked MASTER reference."""

    LOADER_NODE = "171"
    SAMPLER_NODE = "170:169"

    def __init__(
        self,
        configuration: ComfyUIDerivedReferenceConfiguration | None = None,
        *,
        workflows: ManagedWorkflowRegistry | None = None,
        client: XCICCoreClient | None = None,
    ) -> None:
        self.configuration = (
            configuration or ComfyUIDerivedReferenceConfiguration.from_environment()
        )
        self.workflows = workflows or default_workflow_registry()
        self.client = client or XCICCoreClient(self.configuration.base_url)

    @property
    def name(self) -> str:
        return "ComfyUI — Qwen Derived Reference v2.1"

    @property
    def production_capable(self) -> bool:
        return True

    def generate(self, request: DerivedReferenceRequest) -> GeneratedDerivedReference:
        """Compile one runtime job, execute it in ComfyUI, and return the generated PNG."""
        project = request.project_directory
        if project is None:
            raise ComfyUIDerivedReferenceError(
                "The ComfyUI provider requires the active VSCS project directory"
            )
        project = project.resolve(strict=False)
        master = request.master_path.resolve(strict=False)
        if not master.exists() or not master.is_file():
            raise ComfyUIDerivedReferenceError(f"MASTER reference does not exist: {master}")

        workflow = self.workflows.require(self.configuration.workflow_id)
        try:
            prompt = json.loads(workflow.load_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise ComfyUIDerivedReferenceError(
                f"Unable to load VSCS workflow {workflow.workflow_id}: {exc}"
            ) from exc
        if not isinstance(prompt, dict):
            raise ComfyUIDerivedReferenceError("Managed ComfyUI workflow must be a JSON object")
        self._validate_template(prompt)

        job_id = str(uuid4())
        runtime_root = project / ".vscs" / "runtime" / "comfyui"
        job_root = runtime_root / "jobs" / job_id
        queue_root = runtime_root / "queues"
        compiled_root = runtime_root / "compiled"
        output_root = job_root / "output"
        for directory in (job_root, queue_root, compiled_root, output_root):
            directory.mkdir(parents=True, exist_ok=True)

        output_name = f"{request.asset_id}_{request.view.value}_{request.seed:010d}.png"
        queue_path = queue_root / f"derived_reference_{job_id}.json"
        output_path = output_root / output_name
        queue_payload = {
            "jobs": [
                self._queue_job(
                    request,
                    master,
                    output_root,
                    output_name,
                    job_id=job_id,
                )
            ]
        }
        queue_path.write_text(
            json.dumps(queue_payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        loader = prompt[self.LOADER_NODE]
        sampler = prompt[self.SAMPLER_NODE]
        loader["inputs"]["queue_file"] = str(queue_path)
        loader["inputs"]["job_index"] = 0
        loader["inputs"]["quality_mode"] = self.configuration.quality_mode
        sampler["inputs"]["seed"] = request.seed

        compiled_path = compiled_root / f"{workflow.workflow_id.replace('.', '_')}_{job_id}.json"
        compiled_path.write_text(json.dumps(prompt, indent=2), encoding="utf-8")
        manifest_path = job_root / "job.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "workflow_id": workflow.workflow_id,
                    "provider": self.name,
                    "comfyui_url": self.configuration.base_url,
                    "asset_id": request.asset_id,
                    "view": request.view.value,
                    "master_reference": str(master),
                    "queue_file": str(queue_path),
                    "compiled_workflow": str(compiled_path),
                    "expected_output": str(output_path),
                    "seed": request.seed,
                    "requested_width": request.width,
                    "requested_height": request.height,
                    "dimension_policy": "MASTER-derived by FluxKontextImageScale",
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        try:
            self.client.healthcheck()
            self.client.validate_nodes(prompt)
            prompt_id = self.client.submit(prompt)
            self.client.wait(prompt_id, timeout_seconds=self.configuration.timeout_seconds)
        except XCICCoreClientError as exc:
            raise ComfyUIDerivedReferenceError(str(exc)) from exc

        generated_path = self._wait_for_output(output_path, output_root)
        content = generated_path.read_bytes()
        if not content:
            raise ComfyUIDerivedReferenceError(
                f"ComfyUI created an empty derived reference: {generated_path}"
            )
        return GeneratedDerivedReference(
            filename=generated_path.name,
            content=content,
            media_type="image/png",
            provider_name=self.name,
            model="Qwen Image Edit 2511 + Lightning 4-step",
            seed=request.seed,
        )

    def _validate_template(self, prompt: dict[str, Any]) -> None:
        for node_id in (self.LOADER_NODE, self.SAMPLER_NODE):
            node = prompt.get(node_id)
            if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
                raise ComfyUIDerivedReferenceError(
                    f"Managed workflow is missing required node {node_id}"
                )
        queue_value = prompt[self.LOADER_NODE]["inputs"].get("queue_file")
        if queue_value != "__VSCS_QUEUE_FILE__":
            raise ComfyUIDerivedReferenceError(
                "Managed derived-reference workflow must retain __VSCS_QUEUE_FILE__ template marker"
            )

    def _queue_job(
        self,
        request: DerivedReferenceRequest,
        master: Path,
        output_root: Path,
        output_name: str,
        *,
        job_id: str,
    ) -> dict[str, object]:
        """Build the exact job schema consumed by XCICQwenReferenceJobLoader v2.2."""
        return {
            "job_id": job_id,
            "asset_id": request.asset_id,
            "asset_category": self._asset_category(request.asset_id),
            "reference_inputs": [str(master)],
            "positive_prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "generation": {
                "enable_turbo_mode": self.configuration.enable_lightning_lora,
            },
            "generation_policy": {
                "force_standard_mode": self.configuration.quality_mode == "standard",
            },
            "output": {
                "candidate_directory": str(output_root),
                "candidate_filename": output_name,
            },
            "view": request.view.value,
            "seed": request.seed,
        }

    @staticmethod
    def _asset_category(asset_id: str) -> str:
        """Map VSCS asset-ID prefixes to XCIC Qwen preservation profiles."""
        parts = asset_id.upper().split("-")
        prefix = parts[1] if len(parts) > 1 else ""
        return {
            "CHR": "character",
            "SHP": "ship",
            "PLN": "planet",
            "LOC": "location",
            "ENV": "environment",
            "UNI": "uniform",
            "PRP": "prop",
            "TEC": "technology",
            "VEH": "vehicle",
            "EFF": "effect",
        }.get(prefix, "asset")

    @staticmethod
    def _wait_for_output(expected: Path, output_root: Path) -> Path:
        deadline = time.monotonic() + 10.0
        while time.monotonic() <= deadline:
            if expected.exists():
                return expected
            candidates = tuple(output_root.glob("*.png"))
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime_ns)
            time.sleep(0.25)
        raise ComfyUIDerivedReferenceError(
            "ComfyUI reported completion but the derived reference PNG was not written to "
            f"{output_root}"
        )
