"""F5.3: isolated, one-shot managed Qwen GPU inference acceptance.

No CAP service, reference registration, quality-report write, or attempt journal.
The test bundle MUST live outside the active VSCS project. Preparation is
strictly offline; execute requires explicit confirmation and never retries.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vscs.application.caps.guided_edit_live_transport import (
    GuidedEditExecutionError,
    _checked_png,
    _loopback_endpoint,
)
from vscs.application.caps.managed_qwen_edit_inspection import (
    inspect_managed_qwen_edit_workflow,
)
from vscs.application.caps.managed_qwen_model_inventory import (
    validate_managed_qwen_model_choices,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.infrastructure.xcic_core.client import XCICCoreClient

_MAX_IMAGE_BYTES = 40 * 1024 * 1024
_MANIFEST = "acceptance_manifest.json"
_QUEUE = "qwen_acceptance_queue.json"
_GRAPH = "qwen_acceptance_graph.json"
_SOURCE = "source.png"
_OUTPUT = "qwen_acceptance_output.png"
_RESERVATION = "execution_reserved.json"
_RESULT = "acceptance_result.json"


class IsolatedQwenAcceptanceError(RuntimeError):
    """Isolated Qwen evidence or operation is unsafe; never auto-retry."""


@dataclass(frozen=True, slots=True)
class IsolatedQwenAcceptanceBundle:
    bundle_directory: str
    source_sha256: str
    workflow_sha256: str
    graph_sha256: str
    prompt: str
    seed: int


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ensure_external(directory: Path, project_root: Path) -> tuple[Path, Path]:
    if not directory.is_absolute() or not project_root.is_absolute():
        raise IsolatedQwenAcceptanceError("Bundle and project paths must be absolute")
    project = project_root.resolve(strict=True)
    directory = directory.resolve(strict=False)
    if not project.is_dir() or directory == project or project in directory.parents:
        raise IsolatedQwenAcceptanceError("Acceptance bundle must be outside the VSCS project")
    if directory == project.parent or directory in project.parents:
        raise IsolatedQwenAcceptanceError("Acceptance bundle cannot contain the project")
    return directory, project


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IsolatedQwenAcceptanceError(f"Missing or corrupt acceptance evidence: {path}") from exc
    if not isinstance(value, dict):
        raise IsolatedQwenAcceptanceError("Acceptance evidence is not an object")
    return value


def _save_once(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)


def prepare_isolated_qwen_acceptance(
    *,
    source_image: Path,
    project_root: Path,
    bundle_directory: Path,
    prompt: str,
    seed: int = 43,
    workflow_path: Path | None = None,
) -> IsolatedQwenAcceptanceBundle:
    """Create isolated source copy and immutable queue/graph evidence without POST."""
    if not prompt.strip() or len(prompt) > 3000:
        raise IsolatedQwenAcceptanceError("A bounded, explicit edit prompt is required")
    if type(seed) is not int or not 0 <= seed < 2**63:
        raise IsolatedQwenAcceptanceError("Invalid deterministic edit seed")
    bundle, project = _ensure_external(bundle_directory, project_root)
    original = source_image.resolve(strict=True)
    if source_image.is_symlink() or not original.is_file() or project not in original.parents:
        raise IsolatedQwenAcceptanceError("Source must be a regular file in the active project")
    if original.suffix.lower() != ".png":
        raise IsolatedQwenAcceptanceError("Source Candidate must be a PNG image")
    raw = original.read_bytes()
    _checked_png(raw, maximum_bytes=_MAX_IMAGE_BYTES)
    workflow = workflow_path or default_workflow_path()
    inspected = inspect_managed_qwen_edit_workflow(workflow)
    original_graph = _json(workflow)
    if bundle.exists():
        raise IsolatedQwenAcceptanceError("Acceptance directory already exists; never overwrite")
    bundle.mkdir(parents=True, exist_ok=False)
    # The bundle is created exclusively and never points its output at Canonical Assets.
    source_copy = bundle / _SOURCE
    source_copy.write_bytes(raw)
    queue_path = bundle / _QUEUE
    output_path = bundle / _OUTPUT
    graph = copy.deepcopy(original_graph)
    graph["171"]["inputs"]["queue_file"] = str(queue_path)
    graph["171"]["inputs"]["job_index"] = 0
    graph["171"]["inputs"]["quality_mode"] = "standard"
    graph[inspected.sampler_node_id]["inputs"]["seed"] = seed
    queue = {
        "jobs": [{
            "job_id": "isolated-qwen-acceptance",
            "asset_id": "F5_3_DISPOSABLE_GPU_SMOKE_TEST",
            "asset_category": "test",
            "reference_inputs": [str(source_copy)],
            "positive_prompt": prompt.strip(),
            "negative_prompt": "additional objects, changed identity, text overlays",
            "generation": {"enable_turbo_mode": True},
            "generation_policy": {"force_standard_mode": True},
            "seed": seed,
            "output": {
                "candidate_directory": str(bundle),
                "candidate_filename": _OUTPUT,
            },
        }]
    }
    _save_once(queue_path, queue)
    _save_once(bundle / _GRAPH, graph)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "kind": "ISOLATED_QWEN_GPU_ACCEPTANCE_NO_CAP",
        "project_root": str(project),
        "original_source_path": str(original),
        "original_source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_sha256": _hash(source_copy),
        "workflow_sha256": inspected.workflow_sha256,
        "graph_sha256": _hash(bundle / _GRAPH),
        "queue_sha256": _hash(queue_path),
        "prompt": prompt.strip(),
        "seed": seed,
        "output_path": str(output_path),
        "candidate_registration_allowed": False,
        "correction_attempt_allowed": False,
        "canon_mutation_allowed": False,
    }
    _save_once(bundle / _MANIFEST, manifest)
    return IsolatedQwenAcceptanceBundle(
        bundle_directory=str(bundle),
        source_sha256=manifest["source_sha256"],
        workflow_sha256=manifest["workflow_sha256"],
        graph_sha256=manifest["graph_sha256"],
        prompt=prompt.strip(),
        seed=seed,
    )


def _ensure_idle_local_queue(endpoint: str) -> None:
    """Refuse live execution if ComfyUI has any queued or running work."""
    from vscs.application.caps.comfyui_memory_release import _NoRedirects

    url = f"{endpoint}/queue"
    opener = urllib.request.build_opener(_NoRedirects())
    with opener.open(urllib.request.Request(url, method="GET"), timeout=10) as response:
        if response.geturl() != url or not 200 <= response.status < 300:
            raise IsolatedQwenAcceptanceError("ComfyUI queue inspection was rejected")
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise IsolatedQwenAcceptanceError("ComfyUI queue response is oversized")
    try:
        status = json.loads(raw)
    except ValueError as exc:
        raise IsolatedQwenAcceptanceError("ComfyUI returned invalid queue JSON") from exc
    if (
        not isinstance(status, dict)
        or not isinstance(status.get("queue_running"), list)
        or not isinstance(status.get("queue_pending"), list)
    ):
        raise IsolatedQwenAcceptanceError("ComfyUI queue status cannot be verified")
    if status["queue_running"] or status["queue_pending"]:
        raise IsolatedQwenAcceptanceError("ComfyUI is busy; no GPU acceptance submitted")


def execute_isolated_qwen_acceptance(
    *,
    bundle_directory: Path,
    project_root: Path,
    operator_confirmed: bool,
    comfyui_url: str = "http://127.0.0.1:8188",
    timeout_seconds: float = 3600.0,
    client: XCICCoreClient | None = None,
) -> dict[str, Any]:
    """Run exactly one Qwen prompt in the isolated bundle; fail closed on uncertainty."""
    if operator_confirmed is not True:
        raise IsolatedQwenAcceptanceError("Explicit one-shot GPU consent required")
    if not 1 <= timeout_seconds <= 7200:
        raise IsolatedQwenAcceptanceError("Invalid GPU acceptance timeout")
    endpoint = _loopback_endpoint(comfyui_url)
    bundle, project = _ensure_external(bundle_directory, project_root)
    if not bundle.is_dir() or bundle.is_symlink():
        raise IsolatedQwenAcceptanceError("Existing bundle directory is invalid")
    manifest = _json(bundle / _MANIFEST)
    graph = _json(bundle / _GRAPH)
    queue = _json(bundle / _QUEUE)
    original_text = manifest.get("original_source_path")
    original_path = Path(original_text) if isinstance(original_text, str) else project
    if (
        not original_path.is_file()
        or original_path.is_symlink()
        or project not in original_path.resolve(strict=True).parents
    ):
        raise IsolatedQwenAcceptanceError("Original source is outside the active project")
    jobs = queue.get("jobs")
    if not isinstance(jobs, list) or len(jobs) != 1 or not isinstance(jobs[0], dict):
        raise IsolatedQwenAcceptanceError("Acceptance queue must contain exactly one job")
    item = jobs[0]
    if (
        manifest.get("kind") != "ISOLATED_QWEN_GPU_ACCEPTANCE_NO_CAP"
        or manifest.get("project_root") != str(project)
        or manifest.get("source_sha256") != _hash(bundle / _SOURCE)
        or manifest.get("original_source_sha256") != _hash(original_path)
        or manifest.get("graph_sha256") != _hash(bundle / _GRAPH)
        or manifest.get("queue_sha256") != _hash(bundle / _QUEUE)
        or graph.get("171", {}).get("inputs", {}).get("queue_file") != str(bundle / _QUEUE)
        or item.get("reference_inputs") != [str(bundle / _SOURCE)]
        or not isinstance(item.get("output"), dict)
        or item["output"].get("candidate_directory") != str(bundle)
        or item["output"].get("candidate_filename") != _OUTPUT
        or item.get("positive_prompt") != manifest.get("prompt")
        or item.get("seed") != manifest.get("seed")
        or graph.get("170:169", {}).get("inputs", {}).get("seed") != manifest.get("seed")
        or manifest.get("candidate_registration_allowed") is not False
        or manifest.get("correction_attempt_allowed") is not False
        or manifest.get("canon_mutation_allowed") is not False
    ):
        raise IsolatedQwenAcceptanceError("Acceptance bundle or original source changed")
    if any((bundle / name).exists() for name in (_OUTPUT, _RESULT, _RESERVATION)):
        raise IsolatedQwenAcceptanceError("Test already ran or has an unresolved attempt")
    if any(path.is_symlink() for path in bundle.iterdir()):
        raise IsolatedQwenAcceptanceError("Symlink in acceptance bundle is prohibited")
    inspected = inspect_managed_qwen_edit_workflow(default_workflow_path())
    if inspected.workflow_sha256 != manifest.get("workflow_sha256"):
        raise IsolatedQwenAcceptanceError("Managed Qwen source workflow has changed")
    template = _json(default_workflow_path())
    template["171"]["inputs"]["queue_file"] = str(bundle / _QUEUE)
    template["171"]["inputs"]["job_index"] = 0
    template["171"]["inputs"]["quality_mode"] = "standard"
    template[inspected.sampler_node_id]["inputs"]["seed"] = manifest["seed"]
    if graph != template:
        raise IsolatedQwenAcceptanceError("Qwen graph contains unapproved node changes")
    if client is None:
        _ensure_idle_local_queue(endpoint)
    provider = client if client is not None else XCICCoreClient(endpoint)
    provider.healthcheck()
    provider.validate_nodes(graph)
    validate_managed_qwen_model_choices(graph, provider.object_info())
    # Record the one allowed attempt BEFORE a possibly ambiguous network POST.
    _save_once(bundle / _RESERVATION, {
        "status": "RESERVED_UNKNOWN_UNTIL_RESULT",
        "graph_sha256": manifest["graph_sha256"],
        "source_sha256": manifest["source_sha256"],
    })
    started = time.monotonic()
    prompt_id = provider.submit(graph)
    history = provider.wait(prompt_id, timeout_seconds=timeout_seconds)
    output = bundle / _OUTPUT
    if not isinstance(history, dict) or not output.is_file() or output.is_symlink():
        raise IsolatedQwenAcceptanceError("GPU result missing; preserve reservation and logs")
    raw = output.read_bytes()
    width, height = _checked_png(raw, maximum_bytes=_MAX_IMAGE_BYTES)
    if width < 256 or height < 256:
        raise IsolatedQwenAcceptanceError("GPU output below minimum accepted image dimensions")
    if _hash(bundle / _SOURCE) != manifest["source_sha256"]:
        raise IsolatedQwenAcceptanceError("Source changed during GPU execution")
    result: dict[str, Any] = {
        "status": "GPU_OUTPUT_VERIFIED_NO_CAP_CHANGES",
        "prompt_id": prompt_id,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "source_sha256": manifest["source_sha256"],
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "width": width,
        "height": height,
        "workflow_sha256": manifest["workflow_sha256"],
        "output_path": str(output),
        "gpu_peak_vram_mib": None,
        "canon_approved": False,
        "candidate_registered": False,
        "correction_attempt_consumed": False,
    }
    _save_once(bundle / _RESULT, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Isolated managed Qwen GPU acceptance")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--prompt")
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    parser.add_argument("--confirm-one-gpu-run", action="store_true")
    args = parser.parse_args()
    try:
        if args.prepare:
            if args.source is None or args.prompt is None:
                parser.error("--prepare requires --source and --prompt")
            result = prepare_isolated_qwen_acceptance(
                source_image=args.source,
                project_root=args.project_root,
                bundle_directory=args.bundle,
                prompt=args.prompt,
                seed=args.seed,
            )
            print(json.dumps(asdict(result), indent=2, sort_keys=True))
        else:
            result = execute_isolated_qwen_acceptance(
                bundle_directory=args.bundle,
                project_root=args.project_root,
                operator_confirmed=args.confirm_one_gpu_run,
                comfyui_url=args.comfyui_url,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (GuidedEditExecutionError, IsolatedQwenAcceptanceError, RuntimeError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
