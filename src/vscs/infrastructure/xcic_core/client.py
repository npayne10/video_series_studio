"""ComfyUI transport, validation, and monitoring for XCIC Core v1.0."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any
from uuid import uuid4


class XCICCoreClientError(RuntimeError):
    """Raised when ComfyUI cannot validate or execute an XCIC graph."""


class XCICCoreClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = f"vscs-xcic-core-{uuid4()}"

    def object_info(self) -> dict[str, Any]:
        value = self._request("GET", "/object_info")
        if not value:
            raise XCICCoreClientError(
                "Could not read ComfyUI installed node types from /object_info"
            )
        return value

    def healthcheck(self) -> None:
        self._request("GET", "/system_stats")

    def validate_nodes(self, prompt: dict[str, Any]) -> None:
        installed = set(self.object_info())
        unknown = {
            node_id: str(node.get("class_type", ""))
            for node_id, node in prompt.items()
            if not isinstance(node, dict) or node.get("class_type") not in installed
        }
        if unknown:
            details = ", ".join(
                f"#{node_id} {node_type}" for node_id, node_type in sorted(unknown.items())
            )
            raise XCICCoreClientError(
                "XCIC workflow contains node types not installed in ComfyUI: " + details
            )

    def submit(self, prompt: dict[str, Any]) -> str:
        response = self._request("POST", "/prompt", {"prompt": prompt, "client_id": self.client_id})
        prompt_id = response.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise XCICCoreClientError(f"ComfyUI did not return a prompt_id: {response}")
        return prompt_id

    def wait(self, prompt_id: str, timeout_seconds: float = 3600.0) -> dict[str, Any]:
        started = time.monotonic()
        while time.monotonic() - started <= timeout_seconds:
            history = self._request("GET", f"/history/{prompt_id}")
            record = history.get(prompt_id)
            if isinstance(record, dict):
                status = record.get("status", {})
                if isinstance(status, dict) and status.get("status_str") in {"error", "failed"}:
                    raise XCICCoreClientError(
                        "ComfyUI workflow failed: "
                        + json.dumps(status.get("messages", status), ensure_ascii=False)
                    )
                if (isinstance(status, dict) and status.get("completed")) or record.get(
                    "outputs"
                ) is not None:
                    return record
            time.sleep(1.0)
        raise XCICCoreClientError(f"XCIC render timed out after {timeout_seconds:.0f} seconds")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise XCICCoreClientError(
                f"ComfyUI rejected {method} {path} with HTTP {exc.code}: {detail[:8000]}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise XCICCoreClientError(
                f"Unable to communicate with ComfyUI at {self.base_url}: {exc}"
            ) from exc
        if not raw:
            return {}
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise XCICCoreClientError(f"ComfyUI returned invalid JSON: {raw[:1000]}") from exc
        if not isinstance(value, dict):
            raise XCICCoreClientError("ComfyUI returned an unexpected response")
        return value
