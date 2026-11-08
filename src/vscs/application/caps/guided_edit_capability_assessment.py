"""B.5.26F F2: read-only local ComfyUI edit-capability and GPU inventory.

GET-only loopback diagnostics. Never submit prompts, install models, write
project files, or infer edit-readiness from a node name or model filename.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from vscs.infrastructure.xcic.config import XCICConfiguration

_EDIT_TOKENS = ("qwenimageedit", "qwen_image_edit", "inpaint", "imageedit", "image_edit")
_IMAGE_TOKENS = ("loadimage", "reference", "ipadapter")
_CONTROL_TOKENS = ("controlnet", "depth", "canny", "lineart", "segmentation")
_RELEVANT_MODELS = ("qwen", "edit", "inpaint", "controlnet", "flux")
_MAX_ITEMS = 24


@dataclass(frozen=True, slots=True)
class GuidedEditCapabilityReport:
    endpoint: str
    reachable: bool
    devices: tuple[str, ...]
    relevant_nodes: tuple[str, ...]
    model_hints: tuple[str, ...]
    blockers: tuple[str, ...]

    @property
    def ready_for_guided_generation(self) -> bool:
        """F2 is diagnostic only; F3/F4 are required before generating."""
        return False

    def describe(self) -> str:
        return "\n".join(
            [
                "B.5.26F F2 — ComfyUI Guided-Editing Hardware / Capability Audit",
                f"Local ComfyUI: {self.endpoint}",
                f"Read-only endpoint response: {'OK' if self.reachable else 'UNAVAILABLE'}",
                "GPU devices: " + ("; ".join(self.devices) or "not reported"),
                "Relevant installed node names: "
                + (", ".join(self.relevant_nodes) or "none found"),
                "Potential model-name hints: " + (", ".join(self.model_hints) or "none found"),
                "GUIDED EXECUTION READY: NO — source, mask, graph, VRAM and output unverified",
                "No POST requests, model downloads, GPU jobs, paid requests, or attempts.",
                "Blockers:",
                *(f"- {blocker}" for blocker in self.blockers),
            ]
        )


def _loopback_base(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("F2 only permits an HTTP loopback ComfyUI endpoint")
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query:
        raise ValueError("F2 endpoint must not contain credentials, path or query")
    return url.rstrip("/")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never follow a local service redirect to an untrusted host."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _get_json(base: str, path: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(base + path, method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(req, timeout=timeout) as response:
        data = json.load(response)
    if not isinstance(data, dict):
        raise ValueError(f"{path} returned a non-object JSON response")
    return data


def _device_rows(stats: dict[str, Any]) -> tuple[str, ...]:
    rows: list[str] = []
    devices = stats.get("devices")
    if isinstance(devices, list):
        for item in devices:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "unknown GPU"))
            total = item.get("vram_total")
            free = item.get("vram_free")
            if isinstance(total, (int, float)) and not isinstance(total, bool) and total > 0:
                total_gib = total / (1024**3)
                free_gib = (
                    f", free {free / (1024**3):.1f} GiB"
                    if isinstance(free, (int, float)) and not isinstance(free, bool) and free >= 0
                    else ""
                )
                rows.append(f"{name}: total {total_gib:.1f} GiB{free_gib}")
            else:
                rows.append(f"{name}: VRAM unreported")
    return tuple(rows)


def _models_and_nodes(info: dict[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    nodes = sorted(
        name
        for name in info
        if isinstance(name, str)
        and any(
            token in name.lower() for token in (*_EDIT_TOKENS, *_IMAGE_TOKENS, *_CONTROL_TOKENS)
        )
    )
    models: set[str] = set()
    for node in info.values():
        if not isinstance(node, dict):
            continue
        required = node.get("input", {})
        if not isinstance(required, dict):
            continue
        for group in ("required", "optional"):
            fields = required.get(group, {})
            if not isinstance(fields, dict):
                continue
            for field in fields.values():
                if not isinstance(field, list) or not field or not isinstance(field[0], list):
                    continue
                for value in field[0]:
                    if isinstance(value, str) and any(
                        token in value.lower() for token in _RELEVANT_MODELS
                    ):
                        models.add(value)
    return tuple(nodes[:_MAX_ITEMS]), tuple(sorted(models)[:_MAX_ITEMS])


def assess_guided_edit_capability(
    config: XCICConfiguration,
    *,
    timeout: float = 5.0,
) -> GuidedEditCapabilityReport:
    """Use GET /system_stats and GET /object_info only, without side effects."""
    base = _loopback_base(config.comfyui_url)
    try:
        stats = _get_json(base, "/system_stats", timeout)
        info = _get_json(base, "/object_info", timeout)
    except (OSError, urllib.error.URLError, ValueError) as exc:
        return GuidedEditCapabilityReport(
            base,
            False,
            (),
            (),
            (),
            (f"Cannot retrieve both read-only ComfyUI endpoints: {type(exc).__name__}: {exc}",),
        )
    devices = _device_rows(stats)
    nodes, models = _models_and_nodes(info)
    blockers = [
        "Installed node names and model choices do not prove a connected edit graph.",
        "No verified source-image/mask contract or source-preservation test exists.",
        "GPU total/free VRAM is not peak model usage; 16 GiB execution is unverified.",
        "F3 provenance/authority contract and F4 governed provider integration are outstanding.",
    ]
    if not devices:
        blockers.insert(0, "ComfyUI did not report GPU devices.")
    if not nodes:
        blockers.insert(0, "No relevant editing, image-input, or control nodes found.")
    return GuidedEditCapabilityReport(base, True, devices, nodes, models, tuple(blockers))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only F2 ComfyUI capability audit")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    if not 0 < args.timeout <= 30:
        parser.error("--timeout must be between 0 and 30 seconds")
    try:
        report = assess_guided_edit_capability(XCICConfiguration.load(), timeout=args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    print(report.describe())
    return 0 if report.reachable else 1


if __name__ == "__main__":
    raise SystemExit(main())
