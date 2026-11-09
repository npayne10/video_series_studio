"""F4B2 — local-only ComfyUI output transport, with execution held closed.

No production code calls this module to submit an image-edit job. The live
execution approval gate is intentionally unavailable until the actual Qwen
API graph, node schemas and GPU evidence are accepted.
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError

from vscs.application.caps.guided_edit_workflow_binding import GuidedEditBoundWorkflow
from vscs.infrastructure.xcic_core.client import XCICCoreClient


class GuidedEditExecutionError(RuntimeError):
    """A live guided-edit request or returned image is not trustworthy."""


@dataclass(frozen=True, slots=True)
class GuidedEditOutput:
    """Image bytes and provenance only. Not a registered CAP Candidate."""

    content: bytes
    image_sha256: str
    width: int
    height: int
    prompt_id: str
    output_node_id: str
    filename: str
    workflow_sha256: str
    contract_sha256: str

    @property
    def candidate_registered(self) -> bool:
        return False


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        return None


def _loopback_endpoint(url: str) -> str:
    value = urllib.parse.urlsplit(url)
    if (
        value.scheme != "http"
        or value.hostname not in {"127.0.0.1", "localhost", "::1"}
        or value.username is not None
        or value.password is not None
        or value.path not in {"", "/"}
        or value.query
        or value.fragment
    ):
        raise GuidedEditExecutionError("Only a credential-free HTTP loopback ComfyUI is allowed")
    return url.rstrip("/")


def _history_file(history: dict[str, Any], node_id: str) -> tuple[str, str, str]:
    outputs = history.get("outputs")
    if not isinstance(outputs, dict):
        raise GuidedEditExecutionError("ComfyUI history has no output node map")
    selected = outputs.get(node_id)
    if not isinstance(selected, dict):
        raise GuidedEditExecutionError("Approved output node missing from ComfyUI history")
    images = selected.get("images")
    if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
        raise GuidedEditExecutionError("Expected exactly one image in approved output node")
    image = images[0]
    filename = image.get("filename")
    subfolder = image.get("subfolder")
    folder_type = image.get("type")
    if (
        not isinstance(filename, str)
        or not filename.endswith(".png")
        or not filename
        or "/" in filename
        or "\\" in filename
        or filename in {".", ".."}
        or not isinstance(subfolder, str)
        or subfolder
        or folder_type != "output"
    ):
        raise GuidedEditExecutionError("ComfyUI output reference is not a safe root PNG")
    return filename, subfolder, folder_type


def _checked_png(data: bytes, *, maximum_bytes: int) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > maximum_bytes:
        raise GuidedEditExecutionError("ComfyUI result is not a bounded PNG")
    try:
        with Image.open(io.BytesIO(data)) as picture:
            if picture.format != "PNG":
                raise GuidedEditExecutionError("ComfyUI response is not PNG")
            width, height = picture.size
            if not 1 <= width <= 8192 or not 1 <= height <= 8192:
                raise GuidedEditExecutionError("ComfyUI image dimensions are unsupported")
            picture.verify()
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise GuidedEditExecutionError("ComfyUI returned a corrupt PNG") from exc
    return width, height


def fetch_guided_edit_output(
    *,
    comfyui_url: str,
    history: dict[str, Any],
    output_node_id: str,
    prompt_id: str,
    bound: GuidedEditBoundWorkflow,
    timeout: float = 15.0,
    maximum_bytes: int = 40 * 1024 * 1024,
) -> GuidedEditOutput:
    """Retrieve one approved local output. No POST and no CAP persistence."""
    base = _loopback_endpoint(comfyui_url)
    if not prompt_id or not isinstance(output_node_id, str) or output_node_id not in bound.prompt:
        raise GuidedEditExecutionError("Output node ID or prompt provenance is missing")
    if bound.prompt[output_node_id].get("class_type") != "SaveImage":
        raise GuidedEditExecutionError("Approved output node must be SaveImage")
    if not 0 < timeout <= 120 or not 0 < maximum_bytes <= 100 * 1024 * 1024:
        raise GuidedEditExecutionError("Invalid output transport bounds")
    filename, subfolder, folder_type = _history_file(history, output_node_id)
    query = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    request = urllib.request.Request(f"{base}/view?{query}", method="GET")
    opener = urllib.request.build_opener(_RejectRedirects())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read(maximum_bytes + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise GuidedEditExecutionError("Unable to retrieve approved local ComfyUI image") from exc
    width, height = _checked_png(raw, maximum_bytes=maximum_bytes)
    return GuidedEditOutput(
        content=raw,
        image_sha256=hashlib.sha256(raw).hexdigest(),
        width=width,
        height=height,
        prompt_id=prompt_id,
        output_node_id=output_node_id,
        filename=filename,
        workflow_sha256=bound.workflow_sha256,
        contract_sha256=bound.contract_sha256,
    )


class GuidedEditSubmissionGate:
    """Never send POST /prompt until external acceptance authorizes F4B2."""

    def __init__(self, client: XCICCoreClient) -> None:
        self.client = client

    def submit(self, bound: GuidedEditBoundWorkflow) -> str:
        if not bound.execution_authorized:
            raise GuidedEditExecutionError(
                "F4B2 live editing blocked: verified Qwen API graph, operator consent "
                "and hardware acceptance are outstanding"
            )
        raise GuidedEditExecutionError("F4B2 production submission adapter not activated")
