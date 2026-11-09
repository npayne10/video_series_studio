"""B.5.26F F4B2 output security and blocked submission tests."""

import hashlib
import io
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PIL import Image

from vscs.application.caps import guided_edit_live_transport as transport


def _png():
    data = io.BytesIO()
    Image.new("RGB", (20, 16), "gray").save(data, format="PNG")
    return data.getvalue()


def _bound():
    return SimpleNamespace(
        prompt={"7": {"class_type": "SaveImage", "inputs": {"images": ["5", 0]}}},
        workflow_sha256="workflow-hash",
        contract_sha256="contract-hash",
        execution_authorized=False,
    )


def _history(filename="result.png", *, subfolder="", folder_type="output"):
    return {
        "outputs": {
            "7": {"images": [{"filename": filename, "subfolder": subfolder, "type": folder_type}]}
        }
    }


def test_f4b2_retrieves_one_bounded_local_png_without_post(monkeypatch):
    data = _png()
    calls = []

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    class Opener:
        def open(self, request, timeout):
            calls.append((request.full_url, request.get_method(), timeout))
            return Response(data)

    monkeypatch.setattr(transport.urllib.request, "build_opener", lambda *_args: Opener())
    output = transport.fetch_guided_edit_output(
        comfyui_url="http://127.0.0.1:8188",
        history=_history(),
        output_node_id="7",
        prompt_id="prompt-123",
        bound=_bound(),
    )
    assert calls == [
        (
            "http://127.0.0.1:8188/view?filename=result.png&subfolder=&type=output",
            "GET",
            15.0,
        )
    ]
    assert output.content == data
    assert output.image_sha256 == hashlib.sha256(data).hexdigest()
    assert (output.width, output.height) == (20, 16)
    assert not output.candidate_registered
    assert output.workflow_sha256 == "workflow-hash"


@pytest.mark.parametrize(
    "name,subfolder,folder_type",
    [
        ("../escape.png", "", "output"),
        ("nested\\escape.png", "", "output"),
        ("image.jpg", "", "output"),
        ("image.png", "../other", "output"),
        ("image.png", "", "input"),
        ("", "", "output"),
    ],
)
def test_f4b2_blocks_unsafe_history_output(name, subfolder, folder_type):
    with pytest.raises(transport.GuidedEditExecutionError, match="safe root PNG"):
        transport._history_file(_history(name, subfolder=subfolder, folder_type=folder_type), "7")


def test_f4b2_rejects_multiple_outputs():
    history = _history()
    history["outputs"]["7"]["images"].append(history["outputs"]["7"]["images"][0])
    with pytest.raises(transport.GuidedEditExecutionError, match="exactly one"):
        transport._history_file(history, "7")


@pytest.mark.parametrize(
    "url",
    ["http://example.com", "http://192.168.0.1:8188", "https://127.0.0.1:8188"],
)
def test_f4b2_refuses_nonlocal_transport(url):
    with pytest.raises(transport.GuidedEditExecutionError, match="loopback"):
        transport.fetch_guided_edit_output(
            comfyui_url=url,
            history=_history(),
            output_node_id="7",
            prompt_id="prompt",
            bound=_bound(),
        )


def test_f4b2_submission_gate_never_calls_comfyui():
    client = SimpleNamespace(submit=Mock())
    gate = transport.GuidedEditSubmissionGate(client)
    with pytest.raises(transport.GuidedEditExecutionError, match="blocked"):
        gate.submit(_bound())
    client.submit.assert_not_called()


def test_f4b2_no_implicit_authority_from_forged_bound_flag():
    client = SimpleNamespace(submit=Mock())
    gate = transport.GuidedEditSubmissionGate(client)
    forged = SimpleNamespace(execution_authorized=True)
    with pytest.raises(transport.GuidedEditExecutionError, match="not activated"):
        gate.submit(forged)
    client.submit.assert_not_called()


def test_f4b2_rejects_corrupt_output_and_excess_bytes():
    with pytest.raises(transport.GuidedEditExecutionError, match="bounded PNG"):
        transport._checked_png(b"not png", maximum_bytes=1024)
    with pytest.raises(transport.GuidedEditExecutionError, match="bounded PNG"):
        transport._checked_png(_png(), maximum_bytes=8)
