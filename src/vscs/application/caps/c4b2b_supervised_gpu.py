"""C4B.2B: supervised one-shot GPU qualification of a C4B.2A disposable bundle.

This module has no CAP, Candidate, approval or correction-attempt writes.
There is no automatic retry. A reservation is persisted BEFORE launching a
dedicated ComfyUI process, and all results remain outside both VSCS projects.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from vscs.application.caps.c4b2_disposable_runtime import (
    C4B2IsolationError,
    _json_file,
    _safe_path,
    _seal,
    audit_c4b2_external_result,
    inspect_c4b2_offline_runtime_schemas,
    preview_c4b2_isolated_launch,
    verify_c4b2_disposable_bundle,
)
from vscs.application.caps.guided_edit_live_transport import _history_file, _RejectRedirects

_RESERVATION = "c4b2b_execution_reserved.json"
_SUCCESS = "c4b2b_gpu_result.json"
_FAILURE = "c4b2b_execution_failure.json"
_LOG = "c4b2b_comfyui.log"
_MAX_RESPONSE = 16_000_000
_MAX_PROMPT = 2_000_000
_ENDPOINT = "http://127.0.0.1:8298"


class C4B2BQualificationError(RuntimeError):
    """Safety precondition or supervised one-use qualification failure."""


@dataclass(frozen=True, slots=True)
class C4B2BExecutionPlan:
    """Inspection-only fingerprint, not execution permission."""

    bundle_directory: Path
    command: tuple[str, ...]
    source_sha256: str
    mask_sha256: str
    graph_sha256: str
    model_sha256: tuple[tuple[str, str], ...]
    consent_phrase: str
    port: int = 8298

    @property
    def execution_authorized(self) -> bool:
        return False


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _one_use_path(root: Path, name: str, data: dict[str, Any]) -> None:
    """Exclusive, fsynced create: ambiguous failures consume this bundle."""
    with (root / name).open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


def _model_files(
    directory: Path, *, unet_file: Path, clip_file: Path, vae_file: Path
) -> tuple[tuple[str, Path, str], ...]:
    manifest = _json_file(directory / "c4b2_manifest.json")
    graph = _json_file(directory / "c4b2_api_graph.json")
    protected = _safe_path(Path(str(manifest["protected_project_root"])), existing=True)
    disposable = _safe_path(Path(str(manifest["disposable_project_root"])), existing=True)
    selected: list[tuple[str, Path, str]] = []
    for name, raw_path, node_id, field in (
        ("unet", unet_file, "170:161", "unet_name"),
        ("clip", clip_file, "170:162", "clip_name"),
        ("vae", vae_file, "170:146", "vae_name"),
    ):
        path = _safe_path(raw_path, existing=True)
        expected = graph[node_id]["inputs"][field]
        if (
            not path.is_file()
            or path.stat().st_size == 0
            or not isinstance(expected, str)
            or path.name.casefold() != Path(expected).name.casefold()
            or any(
                root == path or root in path.parents for root in (protected, disposable, directory)
            )
        ):
            raise C4B2BQualificationError(f"{name} model is not the isolated reviewed file")
        selected.append((name, path, _hash_file(path)))
    return tuple(selected)


def _protected_asset_snapshot(directory: Path) -> str:
    """Read-only, size-bounded evidence for the specifically protected asset."""
    manifest = _json_file(directory / "c4b2_manifest.json")
    protected = _safe_path(Path(str(manifest["protected_project_root"])), existing=True)
    asset = _safe_path(protected / "Canonical Assets" / "STORY-PRO-B00D168E43", existing=True)
    if not asset.is_dir() or protected not in asset.parents:
        raise C4B2BQualificationError("Protected Diagnostic Console asset is unavailable")
    members: list[tuple[str, int, str]] = []
    total_bytes = 0
    for path in sorted(asset.rglob("*")):
        checked = _safe_path(path, existing=True)
        if checked.is_dir():
            continue
        if not checked.is_file() or asset not in checked.parents:
            raise C4B2BQualificationError("Protected asset contains an unsafe entry")
        size = checked.stat().st_size
        total_bytes += size
        if len(members) >= 1024 or total_bytes > 2 * 1024**3:
            raise C4B2BQualificationError("Protected asset exceeds audit limits")
        members.append((str(checked.relative_to(asset)), size, _hash_file(checked)))
    if not members:
        raise C4B2BQualificationError("Protected asset has no inspectable files")
    return _seal({"asset": str(asset), "files": members})


def inspect_c4b2b_execution_plan(
    directory: Path,
    *,
    python_executable: Path,
    comfyui_main: Path,
    unet_file: Path,
    clip_file: Path,
    vae_file: Path,
) -> C4B2BExecutionPlan:
    """Read-only verification, including hashes of the actual local Qwen models."""
    bundle = verify_c4b2_disposable_bundle(directory)
    command = preview_c4b2_isolated_launch(
        bundle.directory, python_executable=python_executable, comfyui_main=comfyui_main
    )
    if any((bundle.directory / name).exists() for name in (_RESERVATION, _SUCCESS, _FAILURE, _LOG)):
        raise C4B2BQualificationError("C4B.2B bundle already reserved or previously attempted")
    manifest = _json_file(bundle.directory / "c4b2_manifest.json")
    if {item.name for item in (bundle.directory / "input").iterdir()} != {
        manifest.get("source_filename"),
        manifest.get("mask_filename"),
    }:
        raise C4B2BQualificationError("Unreviewed files exist in isolated input")
    for folder in ("output", "temp", "user"):
        if any((bundle.directory / folder).iterdir()):
            raise C4B2BQualificationError("C4B.2B requires empty dedicated runtime directories")
    models = _model_files(
        bundle.directory, unet_file=unet_file, clip_file=clip_file, vae_file=vae_file
    )
    model_digests = tuple((name, sha) for name, _path, sha in models)
    fingerprint = _seal(
        {
            "bundle": bundle.manifest_sha256,
            "command": list(command),
            "models": [(name, str(path), sha) for name, path, sha in models],
        }
    )
    return C4B2BExecutionPlan(
        bundle_directory=bundle.directory,
        command=command,
        source_sha256=bundle.source_sha256,
        mask_sha256=bundle.mask_sha256,
        graph_sha256=bundle.graph_sha256,
        model_sha256=model_digests,
        consent_phrase=f"RUN C4B2B ONCE {fingerprint[:16]}",
    )


def _port_unbound() -> None:
    """Refuse port collisions before creating the one-use reservation."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", 8298))
        except OSError as exc:
            raise C4B2BQualificationError("Dedicated localhost port 8298 is occupied") from exc


def _listener_owned_by(pid: int) -> bool:
    """Fail closed unless the exact ComfyUI child owns 127.0.0.1:8298."""
    try:
        psutil: Any = importlib.import_module("psutil")
        connections = psutil.net_connections(kind="tcp")
    except (ImportError, OSError, RuntimeError) as exc:
        raise C4B2BQualificationError("psutil is required to verify listener PID") from exc
    return any(
        conn.pid == pid
        and conn.status == "LISTEN"
        and conn.laddr
        and conn.laddr.ip == "127.0.0.1"
        and conn.laddr.port == 8298
        for conn in connections
    )


def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    if body is not None and len(body) > _MAX_PROMPT:
        raise C4B2BQualificationError("Prompt exceeds bounded local transport size")
    url = _ENDPOINT + path
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    opener = urllib.request.build_opener(_RejectRedirects())
    try:
        with opener.open(req, timeout=15) as response:
            if response.geturl() != url or response.status != 200:
                raise C4B2BQualificationError("Local ComfyUI response was redirected or rejected")
            raw = response.read(_MAX_RESPONSE + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise C4B2BQualificationError("Local ComfyUI HTTP transport failed") from exc
    if len(raw) > _MAX_RESPONSE:
        raise C4B2BQualificationError("Local ComfyUI JSON response exceeds limit")
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise C4B2BQualificationError("ComfyUI returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise C4B2BQualificationError("ComfyUI response must be a JSON object")
    return data


def _gpu_free_bytes(stats: dict[str, Any]) -> int:
    devices = stats.get("devices")
    if not isinstance(devices, list) or not devices:
        raise C4B2BQualificationError("ComfyUI GPU memory inventory is unavailable")
    free_values: list[int | float] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        if "NVIDIA" not in str(device.get("name", "")).upper():
            continue
        free = device.get("vram_free")
        if isinstance(free, (int, float)) and not isinstance(free, bool) and free >= 0:
            free_values.append(free)
    if not free_values:
        raise C4B2BQualificationError("No NVIDIA GPU memory can be verified")
    return int(min(free_values))


def _wait_until_ready(process: subprocess.Popen[bytes], deadline: float) -> None:
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise C4B2BQualificationError("Dedicated ComfyUI exited before readiness")
        if _listener_owned_by(process.pid):
            return
        time.sleep(0.5)
    raise C4B2BQualificationError("Dedicated ComfyUI startup timed out")


def _wait_for_one_output(
    process: subprocess.Popen[bytes], prompt_id: str, *, timeout_seconds: float
) -> tuple[str, int]:
    deadline = time.monotonic() + timeout_seconds
    minimum_free = 2**63
    while time.monotonic() < deadline:
        if process.poll() is not None or not _listener_owned_by(process.pid):
            raise C4B2BQualificationError("Dedicated ComfyUI process/port ownership was lost")
        minimum_free = min(minimum_free, _gpu_free_bytes(_request("GET", "/system_stats")))
        record = _request("GET", f"/history/{prompt_id}").get(prompt_id)
        if isinstance(record, dict):
            status = record.get("status")
            if isinstance(status, dict) and status.get("status_str") in {"error", "failed"}:
                raise C4B2BQualificationError("ComfyUI reported GPU execution failure")
            if isinstance(status, dict) and status.get("completed") is True:
                name, _subfolder, _kind = _history_file(record, "9")
                return name, minimum_free
        time.sleep(1.0)
    raise C4B2BQualificationError("Supervised Qwen prompt timed out; never auto-retry")


def _stop_owned_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def execute_c4b2b_supervised_once(
    directory: Path,
    *,
    python_executable: Path,
    comfyui_main: Path,
    unet_file: Path,
    clip_file: Path,
    vae_file: Path,
    operator_confirmed: bool,
    consent_phrase: str,
    startup_timeout_seconds: int = 300,
    inference_timeout_seconds: int = 1800,
) -> dict[str, Any]:
    """One explicit disposable GPU attempt, never any CAP or Candidate mutation."""
    if operator_confirmed is not True:
        raise C4B2BQualificationError("Fresh operator approval is required for one GPU attempt")
    if not 30 <= startup_timeout_seconds <= 600 or not 60 <= inference_timeout_seconds <= 3600:
        raise C4B2BQualificationError("Unbounded C4B.2B runtime timeout")
    plan = inspect_c4b2b_execution_plan(
        directory,
        python_executable=python_executable,
        comfyui_main=comfyui_main,
        unet_file=unet_file,
        clip_file=clip_file,
        vae_file=vae_file,
    )
    if consent_phrase != plan.consent_phrase:
        raise C4B2BQualificationError("One-shot consent does not match sealed local evidence")
    protected_before = _protected_asset_snapshot(plan.bundle_directory)
    _port_unbound()
    graph = _json_file(plan.bundle_directory / "c4b2_api_graph.json")
    _one_use_path(
        plan.bundle_directory,
        _RESERVATION,
        {
            "status": "RESERVED_UNKNOWN_UNTIL_VERIFIED",
            "consent_fingerprint": plan.consent_phrase[-16:],
            "source_sha256": plan.source_sha256,
            "mask_sha256": plan.mask_sha256,
            "graph_sha256": plan.graph_sha256,
            "model_sha256": list(plan.model_sha256),
            "port": 8298,
            "candidate_registration_allowed": False,
            "governed_attempt_allowed": False,
        },
    )
    process: subprocess.Popen[bytes] | None = None
    started = time.monotonic()
    try:
        with (plan.bundle_directory / _LOG).open("xb") as log:
            process = subprocess.Popen(
                list(plan.command),
                cwd=Path(plan.command[1]).parent,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                shell=False,
            )
            _wait_until_ready(process, started + startup_timeout_seconds)
            if not _listener_owned_by(process.pid):
                raise C4B2BQualificationError("Dedicated process listener ownership was not proven")
            object_info = _request("GET", "/object_info")
            system_stats = _request("GET", "/system_stats")
            readiness = inspect_c4b2_offline_runtime_schemas(
                plan.bundle_directory, object_info=object_info, system_stats=system_stats
            )
            if not readiness.schema_readiness:
                raise C4B2BQualificationError(
                    "Installed masked Qwen schema/model options are incompatible: "
                    + "; ".join(readiness.missing_requirements)
                )
            initial_free = _gpu_free_bytes(system_stats)
            if initial_free < 8 * 1024**3:
                raise C4B2BQualificationError("Less than 8 GiB GPU memory free; stop before POST")
            queue = _request("GET", "/queue")
            if queue.get("queue_running") != [] or queue.get("queue_pending") != []:
                raise C4B2BQualificationError("Dedicated ComfyUI is not idle")
            if any((plan.bundle_directory / "output").iterdir()):
                raise C4B2BQualificationError("Unexpected pre-submit files in isolated output")
            verify_c4b2_disposable_bundle(plan.bundle_directory)
            repeated_pre_submit = _model_files(
                plan.bundle_directory,
                unet_file=unet_file,
                clip_file=clip_file,
                vae_file=vae_file,
            )
            if tuple((n, s) for n, _p, s in repeated_pre_submit) != plan.model_sha256:
                raise C4B2BQualificationError("Qwen model files changed before GPU submission")
            if not _listener_owned_by(process.pid):
                raise C4B2BQualificationError("Dedicated port was reassigned before GPU submission")
            response = _request("POST", "/prompt", {"prompt": graph, "client_id": str(uuid4())})
            prompt_id = response.get("prompt_id")
            if not isinstance(prompt_id, str) or not 1 <= len(prompt_id) <= 128:
                raise C4B2BQualificationError("ComfyUI submission did not return a valid prompt ID")
            name, minimum_free = _wait_for_one_output(
                process, prompt_id, timeout_seconds=inference_timeout_seconds
            )
            manifest = _json_file(plan.bundle_directory / "c4b2_manifest.json")
            prefix = manifest.get("output_prefix")
            if not isinstance(prefix, str) or not name.startswith(prefix + "_"):
                raise C4B2BQualificationError("GPU output prefix does not match sealed workflow")
            output_path = plan.bundle_directory / "output" / name
            if {path.name for path in output_path.parent.iterdir()} != {name}:
                raise C4B2BQualificationError("Unexpected extra files in isolated GPU output")
            audit = audit_c4b2_external_result(plan.bundle_directory, result_png=output_path)
            if audit.protected_changed_pixels != 0 or audit.editable_changed_pixels == 0:
                raise C4B2BQualificationError("Masked output fails protected/editable pixel checks")
            repeated = _model_files(
                plan.bundle_directory,
                unet_file=unet_file,
                clip_file=clip_file,
                vae_file=vae_file,
            )
            if tuple((n, s) for n, _p, s in repeated) != plan.model_sha256:
                raise C4B2BQualificationError("Qwen model files changed during GPU qualification")
            if _protected_asset_snapshot(plan.bundle_directory) != protected_before:
                raise C4B2BQualificationError("Protected Candidate asset changed during GPU run")
            result: dict[str, Any] = {
                "status": "GPU_PIXELS_VALIDATED_HUMAN_SEMANTICS_PENDING",
                "prompt_id": prompt_id,
                "elapsed_seconds": round(time.monotonic() - started, 2),
                "output_file": str(output_path),
                "result_sha256": audit.result_sha256,
                "source_sha256": audit.source_sha256,
                "mask_sha256": audit.mask_sha256,
                "protected_changed_pixels": audit.protected_changed_pixels,
                "editable_changed_pixels": audit.editable_changed_pixels,
                "vram_free_initial_mib": round(initial_free / (1024**2), 1),
                "vram_free_sampled_low_mib": round(minimum_free / (1024**2), 1),
                "gpu_peak_vram_mib": None,
                "gpu_memory_note": "sampled free VRAM, not true peak process allocation",
                "candidate_registered": False,
                "canon_approved": False,
                "governed_attempt_consumed": False,
                "human_semantic_accepted": None,
            }
            # The dedicated process must be stopped before success is recorded.
            _stop_owned_process(process)
            _one_use_path(plan.bundle_directory, _SUCCESS, result)
            return result
    except BaseException as exc:
        _one_use_path(
            plan.bundle_directory,
            _FAILURE,
            {
                "status": "BLOCKED_OR_UNKNOWN_NO_RETRY",
                "error_type": type(exc).__name__,
                "error": str(exc)[:1200],
                "elapsed_seconds": round(time.monotonic() - started, 2),
            },
        )
        raise
    finally:
        if process is not None:
            _stop_owned_process(process)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="C4B.2B one-shot disposable masked Qwen qualification"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inspect", action="store_true", help="Read-only consent plan; no GPU")
    mode.add_argument(
        "--execute", action="store_true", help="One-shot GPU run; requires fresh consent"
    )
    for name in (
        "bundle",
        "python-executable",
        "comfyui-main",
        "unet-file",
        "clip-file",
        "vae-file",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--confirm-one-gpu-run", action="store_true")
    parser.add_argument("--consent-phrase", default="")
    args = parser.parse_args()
    try:
        if args.inspect:
            plan = inspect_c4b2b_execution_plan(
                args.bundle,
                python_executable=args.python_executable,
                comfyui_main=args.comfyui_main,
                unet_file=args.unet_file,
                clip_file=args.clip_file,
                vae_file=args.vae_file,
            )
            print(json.dumps(asdict(plan), indent=2, sort_keys=True, default=str))
        else:
            result = execute_c4b2b_supervised_once(
                args.bundle,
                python_executable=args.python_executable,
                comfyui_main=args.comfyui_main,
                unet_file=args.unet_file,
                clip_file=args.clip_file,
                vae_file=args.vae_file,
                operator_confirmed=args.confirm_one_gpu_run,
                consent_phrase=args.consent_phrase,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (C4B2IsolationError, C4B2BQualificationError, OSError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
