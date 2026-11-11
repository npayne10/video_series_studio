"""F5.4.1B one-shot, experimental mask-aware Qwen GPU qualification.

Do not run as governed CAP correction. Explicit mask review + GPU consent,
exclusive reservation, idle local ComfyUI and external test-only output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any

from vscs.application.caps.guided_edit_live_transport import (
    _checked_png,
    _loopback_endpoint,
)
from vscs.application.caps.managed_qwen_model_inventory import (
    validate_managed_qwen_model_choices,
)
from vscs.application.caps.qwen_f53_isolated_acceptance import (
    _ensure_external,
    _ensure_idle_local_queue,
    _hash,
    _json,
    _save_once,
)
from vscs.application.caps.qwen_mask_aware_qualification import (
    MaskAwareQualificationError,
    build_experimental_masked_graph,
    confirm_preserved_pixels,
    validate_experimental_graph,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path
from vscs.infrastructure.xcic_core.client import XCICCoreClient


def _upload_mask(endpoint: str, path: Path, filename: str) -> str:
    """Upload approved disposable mask to ComfyUI input, no remote redirects."""
    from vscs.application.caps.comfyui_memory_release import _NoRedirects

    if not filename.startswith("vscs_f541b_") or not filename.endswith(".png"):
        raise MaskAwareQualificationError("Upload filename outside dedicated test namespace")
    raw = path.read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise MaskAwareQualificationError("Mask upload exceeds 4 MiB")
    boundary = "vscs_f541b_mask_upload"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("ascii")
    suffix = (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="type"\r\n\r\n'
        "input\r\n"
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="overwrite"\r\n\r\n'
        "false\r\n"
        f"--{boundary}--\r\n"
    ).encode("ascii")
    url = f"{endpoint}/upload/image"
    request = urllib.request.Request(
        url,
        data=prefix + raw + suffix,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    opener = urllib.request.build_opener(_NoRedirects())
    with opener.open(request, timeout=30) as response:
        if response.geturl() != url or not 200 <= response.status < 300:
            raise MaskAwareQualificationError("ComfyUI mask upload redirected or rejected")
        returned = response.read(8193)
    if len(returned) > 8192:
        raise MaskAwareQualificationError("ComfyUI upload response too large")
    try:
        payload = json.loads(returned)
    except ValueError as exc:
        raise MaskAwareQualificationError("ComfyUI mask upload did not return JSON") from exc
    if (
        not isinstance(payload, dict)
        or payload.get("name") != filename
        or payload.get("type") != "input"
        or payload.get("subfolder", "") not in ("", None)
    ):
        raise MaskAwareQualificationError("ComfyUI uploaded mask identity is not confirmed")
    return filename


def _schema_confirmed(object_info: dict[str, Any]) -> None:
    """Require model and mask/composite schema; no inference from installed names alone."""
    for node_type, expected in (
        ("LoadImageMask", ("image", "channel")),
        ("SetLatentNoiseMask", ("samples", "mask")),
        ("ImageCompositeMasked", ("destination", "source", "x", "y", "mask")),
    ):
        spec = object_info.get(node_type)
        if not isinstance(spec, dict):
            raise MaskAwareQualificationError(f"ComfyUI missing required node {node_type}")
        config = spec.get("input")
        if not isinstance(config, dict):
            raise MaskAwareQualificationError(f"ComfyUI node {node_type} lacks input schema")
        required = config.get("required")
        optional = config.get("optional", {})
        if not isinstance(required, dict) or not isinstance(optional, dict):
            raise MaskAwareQualificationError(f"ComfyUI node {node_type} schema malformed")
        if any(field not in required and field not in optional for field in expected):
            raise MaskAwareQualificationError(f"ComfyUI node {node_type} fields incompatible")
    loader = object_info["LoadImageMask"]["input"]["required"]
    choices = loader["channel"]
    if not isinstance(choices, list) or not choices or "red" not in choices[0]:
        raise MaskAwareQualificationError("ComfyUI mask loader does not offer red channel")


def execute_isolated_mask_qualification(
    *, bundle_directory: Path, project_root: Path,
    operator_confirmed: bool, mask_reviewed: bool,
    comfyui_url: str = "http://127.0.0.1:8188",
    timeout_seconds: float = 3600,
    client: XCICCoreClient | None = None,
    upload_mask: Any = None,
) -> dict[str, Any]:
    """Execute a single isolated experimental graph, never a CAP correction."""
    if operator_confirmed is not True or mask_reviewed is not True:
        raise MaskAwareQualificationError("Separate reviewed-mask and GPU consent required")
    if not 1 <= timeout_seconds <= 7200:
        raise MaskAwareQualificationError("GPU timeout outside accepted bounds")
    endpoint = _loopback_endpoint(comfyui_url)
    bundle, project = _ensure_external(bundle_directory, project_root)
    if not bundle.is_dir() or bundle.is_symlink():
        raise MaskAwareQualificationError("Offline bundle missing or symlinked")
    manifest = _json(bundle / "qualification_manifest.json")
    if manifest.get("kind") != "F541B_OFFLINE_EXPERIMENTAL_MASK_NOT_EXECUTABLE":
        raise MaskAwareQualificationError("Wrong qualification bundle")
    if manifest.get("project_root") != str(project) or manifest.get("bundle_directory") != str(bundle):
        raise MaskAwareQualificationError("Project or bundle changed since preparation")
    if any((bundle / name).exists() for name in (
        "execution_reserved.json", "qualification_result.json",
        "masked_qwen_output.png", "runtime_graph.json", "runtime_queue.json"
    )):
        raise MaskAwareQualificationError("An existing or ambiguous GPU attempt cannot be retried")
    if any(item.is_symlink() for item in bundle.iterdir()):
        raise MaskAwareQualificationError("Bundle symlinks are prohibited")
    source = bundle / "source.png"
    mask = bundle / "mask.png"
    graph_path = bundle / "experimental_masked_api.json"
    original_path = Path(str(manifest.get("original_source_path", "")))
    if (
        original_path.is_symlink()
        or not original_path.is_file()
        or project not in original_path.resolve(strict=True).parents
        or _hash(original_path) != manifest.get("original_source_sha256")
        or _hash(source) != manifest.get("source_sha256")
        or _hash(mask) != manifest.get("mask_sha256")
        or _hash(graph_path) != manifest.get("experimental_graph_sha256")
        or _hash(default_workflow_path()) != manifest.get("template_sha256")
    ):
        raise MaskAwareQualificationError("Source, mask, graph or trusted template changed")
    graph = _json(graph_path)
    validate_experimental_graph(graph)
    if manifest.get("mask_input_filename") != graph["F541B_MASK"]["inputs"]["image"]:
        raise MaskAwareQualificationError("Expected experimental placeholder not present")
    if (
        manifest.get("gpu_execution_authorized") is not False
        or manifest.get("correction_attempt_reserved") is not False
        or manifest.get("candidate_registration_allowed") is not False
    ):
        raise MaskAwareQualificationError("Qualification cannot mutate CAP authority")
    if client is None:
        _ensure_idle_local_queue(endpoint)
    provider = client if client is not None else XCICCoreClient(endpoint)
    provider.healthcheck()
    objects = provider.object_info()
    _schema_confirmed(objects)
    validate_managed_qwen_model_choices(graph, objects)
    filename = "vscs_f541b_" + manifest["mask_sha256"][:20] + ".png"
    # A mask upload is a deliberate external-only side effect; reservation
    # is persisted BEFORE it, so uncertain network outcomes never auto-retry.
    _save_once(bundle / "execution_reserved.json", {
        "status": "RESERVED_UNKNOWN_UNTIL_RESULT",
        "mask_sha256": manifest["mask_sha256"],
        "source_sha256": manifest["source_sha256"],
        "graph_sha256": manifest["experimental_graph_sha256"],
    })
    loader = upload_mask if upload_mask is not None else _upload_mask
    uploaded_name = loader(endpoint, mask, filename)
    if uploaded_name != filename:
        raise MaskAwareQualificationError("ComfyUI mask identity not bound")
    graph["F541B_MASK"]["inputs"]["image"] = uploaded_name
    # Exact independent graph validator, no arbitrary extra edits.
    validate_experimental_graph(graph)
    graph["171"]["inputs"]["queue_file"] = str(bundle / "runtime_queue.json")
    graph["171"]["inputs"]["job_index"] = 0
    graph["171"]["inputs"]["quality_mode"] = "standard"
    graph["170:169"]["inputs"]["seed"] = 43
    queue = {
        "jobs": [{
            "job_id": "isolated-mask-aware-qwen",
            "asset_id": "F541B_DISPOSABLE_NOT_CAP",
            "asset_category": "test",
            "reference_inputs": [str(source)],
            "positive_prompt": (
                "Preserve the existing console. Correct the rotary dial to sit "
                "within a visibly recessed well. Do not change features outside "
                "the supplied editable region."
            ),
            "negative_prompt": "additional objects, changed identity, text overlays",
            "generation": {"enable_turbo_mode": True},
            "generation_policy": {"force_standard_mode": True},
            "seed": 43,
            "output": {
                "candidate_directory": str(bundle),
                "candidate_filename": "masked_qwen_output.png",
            },
        }]
    }
    _save_once(bundle / "runtime_graph.json", graph)
    _save_once(bundle / "runtime_queue.json", queue)
    provider.validate_nodes(graph)
    started = time.monotonic()
    prompt_id = provider.submit(graph)
    history = provider.wait(prompt_id, timeout_seconds=timeout_seconds)
    output = bundle / "masked_qwen_output.png"
    if not isinstance(history, dict) or not output.is_file() or output.is_symlink():
        raise MaskAwareQualificationError("No verified GPU output; preserve reservation")
    output_bytes = output.read_bytes()
    _checked_png(output_bytes, maximum_bytes=40 * 1024 * 1024)
    if _hash(source) != manifest["source_sha256"] or _hash(mask) != manifest["mask_sha256"]:
        raise MaskAwareQualificationError("Mask/source changed during GPU inference")
    audit = confirm_preserved_pixels(source, output, mask)
    status = (
        "SPATIAL_PIXEL_PRESERVATION_VERIFIED"
        if audit["outside_mask_pixels_identical"]
        else "SPATIAL_PRESERVATION_FAILED"
    )
    result = {
        "status": status,
        "prompt_id": prompt_id,
        "elapsed_seconds": round(time.monotonic() - started, 2),
        "mask_filename": uploaded_name,
        "source_sha256": manifest["source_sha256"],
        "output_sha256": _hash(output),
        "graph_sha256": _hash(bundle / "runtime_graph.json"),
        "protected_changed_pixels": audit["protected_changed_pixels"],
        "outside_mask_pixels_identical": audit["outside_mask_pixels_identical"],
        "semantic_geometry_correct": None,
        "gpu_peak_vram_mib": None,
        "candidate_registered": False,
        "canon_approved": False,
        "correction_attempt_consumed": False,
    }
    _save_once(bundle / "qualification_result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot isolated masked Qwen GPU qualification")
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--comfyui-url", default="http://127.0.0.1:8188")
    parser.add_argument("--confirm-reviewed-mask", action="store_true")
    parser.add_argument("--confirm-one-gpu-run", action="store_true")
    args = parser.parse_args()
    try:
        result = execute_isolated_mask_qualification(
            bundle_directory=args.bundle, project_root=args.project_root,
            operator_confirmed=args.confirm_one_gpu_run,
            mask_reviewed=args.confirm_reviewed_mask,
            comfyui_url=args.comfyui_url,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": f"{type(exc).__name__}: {exc}"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
