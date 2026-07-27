"""Minimal ComfyUI HTTP client used by the XCIC rendering engine."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from uuid import uuid4


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI cannot accept or complete a workflow."""


class ComfyUIClient:
    """Submit API-format workflows and wait for their completion."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid4())

    def healthcheck(self) -> None:
        self._json_request("GET", "/system_stats")

    def submit_workflow(self, workflow: Path | dict[str, Any]) -> str:
        if isinstance(workflow, Path):
            path = workflow.expanduser().resolve(strict=False)
            if not path.is_file():
                raise ComfyUIError(f"ComfyUI API workflow not found: {path}")
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ComfyUIError(f"Unable to read ComfyUI API workflow {path}: {exc}") from exc
        else:
            value = workflow
        if not isinstance(value, dict):
            raise ComfyUIError("The ComfyUI API workflow must be a JSON object")
        response = self._json_request(
            "POST", "/prompt", {"prompt": value, "client_id": self.client_id}
        )
        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyUIError(f"ComfyUI did not return a prompt_id: {response}")
        return prompt_id

    def wait_for_completion(self, prompt_id: str, timeout_seconds: float = 900.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            history = self._json_request("GET", f"/history/{prompt_id}")
            record = history.get(prompt_id)
            if isinstance(record, dict):
                status = record.get("status", {})
                if isinstance(status, dict) and status.get("status_str") == "error":
                    raise ComfyUIError(f"ComfyUI workflow failed: {status}")
                if record.get("outputs") is not None:
                    return record
            time.sleep(1.0)
        raise ComfyUIError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    def _json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ComfyUIError(f"Unable to communicate with ComfyUI at {self.base_url}: {exc}") from exc
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ComfyUIError(f"ComfyUI returned invalid JSON: {raw[:300]}") from exc
        if not isinstance(value, dict):
            raise ComfyUIError("ComfyUI returned an unexpected response")
        return value
