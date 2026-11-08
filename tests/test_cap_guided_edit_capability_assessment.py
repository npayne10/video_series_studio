"""B.5.26F F2 — local-only, GET-only capability inspection regression."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps import guided_edit_capability_assessment as audit


def _config(url="http://127.0.0.1:8188"):
    return SimpleNamespace(comfyui_url=url)


def test_f2_parses_device_vram_and_model_options_without_claiming_readiness(monkeypatch):
    paths = []

    def get(base, path, timeout):
        paths.append((base, path, timeout))
        if path == "/system_stats":
            return {
                "devices": [
                    {
                        "name": "RTX 5060 Ti",
                        "vram_total": 16 * 1024**3,
                        "vram_free": 12 * 1024**3,
                    }
                ]
            }
        return {
            "QwenImageEdit": {
                "input": {
                    "required": {
                        "model": [["qwen_image_edit_fp8.safetensors", "other.safetensors"]]
                    }
                }
            },
            "LoadImage": {"input": {"required": {}}},
        }

    monkeypatch.setattr(audit, "_get_json", get)
    report = audit.assess_guided_edit_capability(_config())
    assert paths == [
        ("http://127.0.0.1:8188", "/system_stats", 5.0),
        ("http://127.0.0.1:8188", "/object_info", 5.0),
    ]
    assert report.reachable
    assert "total 16.0 GiB, free 12.0 GiB" in report.devices[0]
    assert "QwenImageEdit" in report.relevant_nodes
    assert "qwen_image_edit_fp8.safetensors" in report.model_hints
    assert not report.ready_for_guided_generation
    assert "GUIDED EXECUTION READY: NO" in report.describe()


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8188",
        "http://example.com",
        "http://192.168.1.4:8188",
        "http://user:password@127.0.0.1:8188",
        "http://127.0.0.1:8188/prompt",
        "http://127.0.0.1:8188/?token=test",
    ],
)
def test_f2_rejects_nonlocal_or_unsafe_endpoints(monkeypatch, url):
    fetch = Mock()
    monkeypatch.setattr(audit, "_get_json", fetch)
    with pytest.raises(ValueError, match="F2"):
        audit.assess_guided_edit_capability(_config(url))
    fetch.assert_not_called()


def test_f2_unreachable_comfyui_fails_closed(monkeypatch):
    def fail(*args):
        raise OSError("connection refused")

    monkeypatch.setattr(audit, "_get_json", fail)
    report = audit.assess_guided_edit_capability(_config())
    assert not report.reachable
    assert not report.ready_for_guided_generation
    assert not report.model_hints


def test_f2_reads_json_through_get_only_and_refuses_redirect(monkeypatch):
    requests = []

    class Response(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    class Opener:
        def open(self, req, timeout):
            requests.append((req.full_url, req.get_method(), timeout))
            return Response(b'{"devices":[]}')

    monkeypatch.setattr(audit.urllib.request, "build_opener", lambda *_handlers: Opener())
    result = audit._get_json("http://127.0.0.1:8188", "/system_stats", 3.0)
    assert result == {"devices": []}
    assert requests == [("http://127.0.0.1:8188/system_stats", "GET", 3.0)]


def test_f2_handles_missing_devices_and_model_schema(monkeypatch):
    monkeypatch.setattr(
        audit,
        "_get_json",
        lambda _base, path, _timeout: {} if path == "/system_stats" else {"node": {}},
    )
    report = audit.assess_guided_edit_capability(_config())
    assert report.reachable
    assert not report.devices
    assert not report.relevant_nodes
    assert not report.model_hints
    assert not report.ready_for_guided_generation
