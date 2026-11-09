"""F5 read-only Qwen Image Edit hardware readiness inventory.

No POST, model load, attempt reservation, CAP mutation or GPU execution.
Run with: python -m vscs.application.caps.qwen_f5_preflight
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from vscs.application.caps.guided_edit_live_transport import _loopback_endpoint
from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.managed_qwen_model_inventory import (
    validate_managed_qwen_model_choices,
)
from vscs.infrastructure.xcic_core.client import XCICCoreClient


@dataclass(frozen=True, slots=True)
class QwenF5PreflightReport:
    """Portable, non-authorizing record of read-only readiness checks."""

    graph_sha256: str
    workflow_path: str
    endpoint: str
    comfyui_reachable: bool
    nodes_and_models_available: bool
    gpu_inventory: tuple[dict[str, str], ...]
    gpu_inventory_error: str | None
    errors: tuple[str, ...]
    status: str

    @property
    def execution_authorized(self) -> bool:
        return False


def default_workflow_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "workflows"
        / "image"
        / "VSCS_Qwen_Derived_Reference_Workflow_API_v2.1.json"
    )


def _gpu_inventory() -> tuple[tuple[dict[str, str], ...], str | None]:
    cmd = (
        "nvidia-smi",
        "--query-gpu=name,memory.total,memory.free,driver_version",
        "--format=csv,noheader,nounits",
    )
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (), f"GPU inventory unavailable: {type(exc).__name__}: {exc}"
    if result.returncode != 0:
        return (), f"nvidia-smi failed (exit {result.returncode}): {result.stderr.strip()}"
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = [piece.strip() for piece in line.split(",")]
        if len(fields) != 4 or not all(fields):
            return (), "nvidia-smi returned an unrecognized GPU inventory format"
        rows.append(
            {
                "name": fields[0],
                "memory_total_mib": fields[1],
                "memory_free_mib": fields[2],
                "driver_version": fields[3],
            }
        )
    if not rows:
        return (), "nvidia-smi reported no GPUs"
    return tuple(rows), None


def inspect_qwen_f5_hardware(
    *,
    workflow_path: Path | None = None,
    comfyui_url: str = "http://127.0.0.1:8188",
    client: XCICCoreClient | None = None,
) -> QwenF5PreflightReport:
    """Collect read-only ComfyUI and GPU evidence, fail closed on unknowns."""
    base = _loopback_endpoint(comfyui_url)
    workflow = workflow_path if workflow_path is not None else default_workflow_path()
    errors: list[str] = []
    digest = ""
    reachable = False
    models_ok = False
    try:
        inspected = inspect_managed_qwen_edit_workflow(workflow)
        digest = inspected.workflow_sha256
        graph = json.loads(workflow.read_text(encoding="utf-8"))
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f"Managed Qwen workflow: {type(exc).__name__}: {exc}")
        graph = None
    provider = client if client is not None else XCICCoreClient(base)
    try:
        provider.healthcheck()
        reachable = True
        if isinstance(graph, dict):
            provider.validate_nodes(graph)
            validate_managed_qwen_model_choices(graph, provider.object_info())
            models_ok = True
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f"Local ComfyUI preflight: {type(exc).__name__}: {exc}")
    gpu, gpu_error = _gpu_inventory()
    if gpu_error is not None:
        errors.append(gpu_error)
    return QwenF5PreflightReport(
        graph_sha256=digest,
        workflow_path=str(workflow),
        endpoint=base,
        comfyui_reachable=reachable,
        nodes_and_models_available=models_ok,
        gpu_inventory=gpu,
        gpu_inventory_error=gpu_error,
        errors=tuple(errors),
        status="PREFLIGHT_READY_NO_GPU_INFERENCE" if not errors and models_ok else "BLOCKED",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only Qwen F5 hardware readiness inventory")
    parser.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    try:
        report = inspect_qwen_f5_hardware(comfyui_url=args.comfyui_url)
        print(json.dumps(asdict(report), indent=2, sort_keys=True))
        return 0 if report.status == "PREFLIGHT_READY_NO_GPU_INFERENCE" else 2
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
