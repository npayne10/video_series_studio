"""F5.2: local ComfyUI memory release is consented and idle-queue guarded."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps import comfyui_memory_release as cleanup


class _Response:
    def __init__(self, url, body=b"", status=200):
        self.url = url
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def geturl(self):
        return self.url

    def read(self, _size):
        return self.body


def _opener(monkeypatch, *, running=None, pending=None, queue=None):
    responses = []
    if queue is None:
        queue = {
            "queue_running": [] if running is None else running,
            "queue_pending": [] if pending is None else pending,
        }
    calls = []

    class FakeOpener:
        def open(self, request, *, timeout):
            calls.append((request, timeout))
            if request.get_method() == "GET":
                return _Response(
                    "http://127.0.0.1:8188/queue",
                    json.dumps(queue).encode("utf-8"),
                )
            responses.append(request.data)
            return _Response("http://127.0.0.1:8188/free")

    monkeypatch.setattr(cleanup.urllib.request, "build_opener", lambda *_a: FakeOpener())
    return calls, responses


def test_free_models_only_when_queue_empty_and_confirmed(monkeypatch):
    calls, posts = _opener(monkeypatch)
    result = cleanup.release_idle_comfyui_memory(operator_confirmed=True)
    assert result.request_accepted
    assert result.queue_empty_before_release
    assert len(calls) == 2
    assert [request.get_method() for request, _ in calls] == ["GET", "POST"]
    assert json.loads(posts[0]) == {"unload_models": True, "free_memory": True}


def test_no_confirmation_never_contacts_server(monkeypatch):
    calls, _posts = _opener(monkeypatch)
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="confirmation"):
        cleanup.release_idle_comfyui_memory(operator_confirmed=False)
    assert not calls


@pytest.mark.parametrize(
    ("running", "pending"),
    [(["job"], []), ([], ["job"]), (["job"], ["job"])],
)
def test_busy_queue_refuses_release(monkeypatch, running, pending):
    calls, posts = _opener(monkeypatch, running=running, pending=pending)
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="busy"):
        cleanup.release_idle_comfyui_memory(operator_confirmed=True)
    assert len(calls) == 1
    assert not posts


@pytest.mark.parametrize(
    "queue",
    [{"queue_running": []}, {"queue_running": None, "queue_pending": []}, {}],
)
def test_unrecognized_queue_schema_fails_closed(monkeypatch, queue):
    calls, posts = _opener(monkeypatch, queue=queue)
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="queue"):
        cleanup.release_idle_comfyui_memory(operator_confirmed=True)
    assert len(calls) == 1
    assert not posts


def test_remote_comfyui_rejected(monkeypatch):
    calls, posts = _opener(monkeypatch)
    with pytest.raises(RuntimeError, match="loopback"):
        cleanup.release_idle_comfyui_memory(
            comfyui_url="http://192.168.0.9:8188",
            operator_confirmed=True,
        )
    assert not calls
    assert not posts


def test_queue_redirect_is_rejected_without_post(monkeypatch):
    posts = []

    class RedirectOpener:
        def open(self, request, *, timeout):
            posts.append(request.get_method())
            return _Response("http://example.org/queue", b"{}")

    monkeypatch.setattr(
        cleanup.urllib.request, "build_opener", lambda *_a: RedirectOpener()
    )
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="redirected"):
        cleanup.release_idle_comfyui_memory(operator_confirmed=True)
    assert posts == ["GET"]


def test_free_http_failure_does_not_report_success(monkeypatch):
    calls = []

    class RejectedOpener:
        def open(self, request, *, timeout):
            calls.append(request.get_method())
            if request.get_method() == "GET":
                return _Response(
                    "http://127.0.0.1:8188/queue",
                    b'{"queue_running":[],"queue_pending":[]}',
                )
            return _Response("http://127.0.0.1:8188/free", status=503)

    monkeypatch.setattr(
        cleanup.urllib.request, "build_opener", lambda *_a: RejectedOpener()
    )
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="rejected"):
        cleanup.release_idle_comfyui_memory(operator_confirmed=True)
    assert calls == ["GET", "POST"]


def test_malformed_json_refused(monkeypatch):
    class BadOpener:
        def open(self, request, *, timeout):
            return _Response("http://127.0.0.1:8188/queue", b"bad json")

    monkeypatch.setattr(cleanup.urllib.request, "build_opener", lambda *_a: BadOpener())
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="invalid queue JSON"):
        cleanup.release_idle_comfyui_memory(operator_confirmed=True)


def test_timeout_is_bounded(monkeypatch):
    calls, _posts = _opener(monkeypatch)
    with pytest.raises(cleanup.ComfyMemoryReleaseError, match="timeout"):
        cleanup.release_idle_comfyui_memory(
            operator_confirmed=True, timeout_seconds=45
        )
    assert not calls
