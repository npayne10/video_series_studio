"""Operator-confirmed ComfyUI model cache release for idle local servers.

The /free call is deliberately isolated from CAP provenance, candidates
and generation. It checks the live queue immediately before the POST;
ComfyUI itself cannot provide a cross-client atomic queue/release lock.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from vscs.application.caps.guided_edit_live_transport import _loopback_endpoint


class ComfyMemoryReleaseError(RuntimeError):
    """A local ComfyUI cache release is unsafe, failed or unconfirmed."""


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


@dataclass(frozen=True, slots=True)
class ComfyMemoryReleaseReport:
    """Accepted cache release request, not proof of reclaimed GPU memory."""

    endpoint: str
    queue_empty_before_release: bool
    request_accepted: bool


def _json_response(response: Any, *, endpoint: str) -> dict[str, Any]:
    if response.geturl() != endpoint:
        raise ComfyMemoryReleaseError("ComfyUI memory request was redirected")
    if not 200 <= response.status < 300:
        raise ComfyMemoryReleaseError("ComfyUI returned an unsuccessful HTTP status")
    data = response.read(1024 * 1024 + 1)
    if len(data) > 1024 * 1024:
        raise ComfyMemoryReleaseError("ComfyUI queue response is too large")
    try:
        result = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        raise ComfyMemoryReleaseError("ComfyUI returned invalid queue JSON") from exc
    if not isinstance(result, dict):
        raise ComfyMemoryReleaseError("ComfyUI queue has an invalid shape")
    return result


def release_idle_comfyui_memory(
    *,
    comfyui_url: str = "http://127.0.0.1:8188",
    operator_confirmed: bool,
    timeout_seconds: float = 10.0,
) -> ComfyMemoryReleaseReport:
    """Release cached local models only after explicit approval and idle queue.

    A queue change after the GET cannot be prevented by this client. The
    operation is intentionally never triggered automatically by preflight.
    """
    if operator_confirmed is not True:
        raise ComfyMemoryReleaseError("Explicit operator confirmation required")
    base = _loopback_endpoint(comfyui_url)
    if not 0 < timeout_seconds <= 30:
        raise ComfyMemoryReleaseError("Invalid ComfyUI memory release timeout")
    opener = urllib.request.build_opener(_NoRedirects())
    queue_url = f"{base}/queue"
    try:
        with opener.open(
            urllib.request.Request(queue_url, method="GET"),
            timeout=timeout_seconds,
        ) as response:
            queue = _json_response(response, endpoint=queue_url)
    except (OSError, urllib.error.URLError) as exc:
        raise ComfyMemoryReleaseError("Cannot verify ComfyUI queue is idle") from exc
    if set(queue) != {"queue_running", "queue_pending"}:
        raise ComfyMemoryReleaseError("ComfyUI queue schema is unknown; memory release blocked")
    running = queue["queue_running"]
    pending = queue["queue_pending"]
    if not isinstance(running, list) or not isinstance(pending, list):
        raise ComfyMemoryReleaseError("ComfyUI queue entries are invalid")
    if running or pending:
        raise ComfyMemoryReleaseError(
            f"ComfyUI is busy: {len(running)} running, {len(pending)} pending"
        )
    payload = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
    free_url = f"{base}/free"
    request = urllib.request.Request(
        free_url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            if response.geturl() != free_url or not 200 <= response.status < 300:
                raise ComfyMemoryReleaseError("ComfyUI memory release was redirected or rejected")
            if len(response.read(1024 * 1024 + 1)) > 1024 * 1024:
                raise ComfyMemoryReleaseError("ComfyUI memory response is too large")
    except (OSError, urllib.error.URLError) as exc:
        raise ComfyMemoryReleaseError(
            "ComfyUI memory release failed or outcome is uncertain"
        ) from exc
    return ComfyMemoryReleaseReport(
        endpoint=base,
        queue_empty_before_release=True,
        request_accepted=True,
    )
