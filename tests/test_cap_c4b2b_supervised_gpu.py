"""C4B.2B execution-contract tests: never start a real ComfyUI or GPU job."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vscs.application.caps import c4b2b_supervised_gpu as gpu


def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "external_bundle"
    root.mkdir()
    for name in ("input", "output", "temp", "user"):
        (root / name).mkdir()
    protected = tmp_path / "protected_project"
    protected.mkdir()
    canonical_asset = protected / "Canonical Assets" / "STORY-PRO-B00D168E43"
    canonical_asset.mkdir(parents=True)
    (canonical_asset / "protected_marker.txt").write_text("unaltered")
    disposable = tmp_path / "disposable_project"
    disposable.mkdir()
    graph = {
        "170:161": {"inputs": {"unet_name": "model_unet.safetensors"}},
        "170:162": {"inputs": {"clip_name": "model_clip.safetensors"}},
        "170:146": {"inputs": {"vae_name": "model_vae.safetensors"}},
    }
    (root / "c4b2_api_graph.json").write_text(json.dumps(graph))
    manifest = {
        "protected_project_root": str(protected),
        "disposable_project_root": str(disposable),
        "output_prefix": "C4B_DISPOSABLE_QUALIFICATION",
        "source_filename": "c4b_source_fake.png",
        "mask_filename": "c4b_mask_fake.png",
    }
    (root / "c4b2_manifest.json").write_text(json.dumps(manifest))
    for name in ("c4b_source_fake.png", "c4b_mask_fake.png"):
        (root / "input" / name).write_bytes(b"fake-test-only-PNG-evidence")
    models = tmp_path / "model_files"
    models.mkdir()
    unet, clip, vae = (models / f"model_{kind}.safetensors" for kind in ("unet", "clip", "vae"))
    for path in (unet, clip, vae):
        path.write_bytes(b"test-only-weights")
    python = tmp_path / "python.exe"
    main = tmp_path / "main.py"
    python.write_bytes(b"test")
    main.write_bytes(b"test")
    fake_bundle = SimpleNamespace(
        directory=root,
        manifest_sha256="a" * 64,
        source_sha256="b" * 64,
        mask_sha256="c" * 64,
        graph_sha256="d" * 64,
    )
    monkeypatch.setattr(gpu, "verify_c4b2_disposable_bundle", lambda path: fake_bundle)
    monkeypatch.setattr(
        gpu,
        "preview_c4b2_isolated_launch",
        lambda *_args, **_kwargs: (str(python), str(main), "--port", "8298"),
    )
    params = {
        "python_executable": python,
        "comfyui_main": main,
        "unet_file": unet,
        "clip_file": clip,
        "vae_file": vae,
    }
    return root, protected, params


def test_c4b2b_plan_is_read_only_and_bound_to_models(tmp_path, monkeypatch):
    directory, protected, params = _sandbox(tmp_path, monkeypatch)
    before = set(directory.iterdir())
    plan = gpu.inspect_c4b2b_execution_plan(directory, **params)
    assert plan.port == 8298
    assert plan.graph_sha256 == "d" * 64
    assert not plan.execution_authorized
    assert plan.consent_phrase.startswith("RUN C4B2B ONCE ")
    assert len(plan.model_sha256) == 3
    assert set(directory.iterdir()) == before
    protected_marker = (
        protected / "Canonical Assets" / "STORY-PRO-B00D168E43" / "protected_marker.txt"
    )
    assert protected_marker.read_text() == "unaltered"
    params["clip_file"].write_bytes(b"different-weight-content")
    changed = gpu.inspect_c4b2b_execution_plan(directory, **params)
    assert changed.consent_phrase != plan.consent_phrase


def test_c4b2b_refuses_protected_models_and_reserved_bundle(tmp_path, monkeypatch):
    directory, protected, params = _sandbox(tmp_path, monkeypatch)
    model = protected / "model_unet.safetensors"
    model.write_bytes(b"wrong-scope")
    with pytest.raises(gpu.C4B2BQualificationError, match="isolated reviewed file"):
        gpu.inspect_c4b2b_execution_plan(directory, **{**params, "unet_file": model})
    (directory / "c4b2b_execution_reserved.json").write_text("{}")
    with pytest.raises(gpu.C4B2BQualificationError, match="already reserved"):
        gpu.inspect_c4b2b_execution_plan(directory, **params)


def test_c4b2b_rejects_unreviewed_input_and_nonempty_output(tmp_path, monkeypatch):
    directory, _protected, params = _sandbox(tmp_path, monkeypatch)
    extra = directory / "input" / "unreviewed.png"
    extra.write_bytes(b"extra")
    with pytest.raises(gpu.C4B2BQualificationError, match="Unreviewed files"):
        gpu.inspect_c4b2b_execution_plan(directory, **params)
    extra.unlink()
    (directory / "output" / "old.png").write_bytes(b"old")
    with pytest.raises(gpu.C4B2BQualificationError, match="empty dedicated"):
        gpu.inspect_c4b2b_execution_plan(directory, **params)


def test_c4b2b_read_only_protected_asset_snapshot_detects_mutation(tmp_path, monkeypatch):
    directory, protected, _params = _sandbox(tmp_path, monkeypatch)
    original = gpu._protected_asset_snapshot(directory)
    protected_file = (
        protected / "Canonical Assets" / "STORY-PRO-B00D168E43" / "protected_marker.txt"
    )
    protected_file.write_text("modified")
    assert gpu._protected_asset_snapshot(directory) != original


@pytest.mark.parametrize("stats", [{}, {"devices": []}, {"devices": [{"name": "CPU"}]}])
def test_c4b2b_requires_coherent_nvidia_memory(stats):
    with pytest.raises(gpu.C4B2BQualificationError, match="GPU memory"):
        gpu._gpu_free_bytes(stats)


def test_c4b2b_requires_fresh_exact_consent_before_any_reservation(tmp_path, monkeypatch):
    directory, _protected, params = _sandbox(tmp_path, monkeypatch)
    plan = gpu.inspect_c4b2b_execution_plan(directory, **params)
    with pytest.raises(gpu.C4B2BQualificationError, match="Fresh operator approval"):
        gpu.execute_c4b2b_supervised_once(
            directory, **params, operator_confirmed=False, consent_phrase=plan.consent_phrase
        )
    with pytest.raises(gpu.C4B2BQualificationError, match="does not match"):
        gpu.execute_c4b2b_supervised_once(
            directory, **params, operator_confirmed=True, consent_phrase="invalid"
        )
    assert not (directory / "c4b2b_execution_reserved.json").exists()


def test_c4b2b_refuses_execution_if_port_busy_before_reservation(tmp_path, monkeypatch):
    directory, _protected, params = _sandbox(tmp_path, monkeypatch)
    plan = gpu.inspect_c4b2b_execution_plan(directory, **params)

    def busy():
        raise gpu.C4B2BQualificationError("Dedicated localhost port 8298 is occupied")

    monkeypatch.setattr(gpu, "_port_unbound", busy)
    with pytest.raises(gpu.C4B2BQualificationError, match="port 8298 is occupied"):
        gpu.execute_c4b2b_supervised_once(
            directory, **params, operator_confirmed=True, consent_phrase=plan.consent_phrase
        )
    assert not (directory / "c4b2b_execution_reserved.json").exists()


def test_c4b2b_one_shot_reservation_precedes_any_process_launch(tmp_path, monkeypatch):
    directory, protected, params = _sandbox(tmp_path, monkeypatch)
    plan = gpu.inspect_c4b2b_execution_plan(directory, **params)
    monkeypatch.setattr(gpu, "_port_unbound", lambda: None)
    observed = []

    class FakeProcess:
        pid = 12345
        stopped = False

        def poll(self):
            return 0 if self.stopped else None

        def terminate(self):
            observed.append("terminated")
            self.stopped = True

        def wait(self, timeout):
            return 0

    def fake_popen(*_args, **_kwargs):
        assert (directory / "c4b2b_execution_reserved.json").exists()
        observed.append("launched")
        return FakeProcess()

    monkeypatch.setattr(gpu.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(gpu, "_wait_until_ready", lambda *_args: None)
    monkeypatch.setattr(gpu, "_listener_owned_by", lambda _pid: True)
    monkeypatch.setattr(gpu, "_gpu_free_bytes", lambda _stats: 14 * 1024**3)
    monkeypatch.setattr(
        gpu,
        "inspect_c4b2_offline_runtime_schemas",
        lambda *_args, **_kwargs: SimpleNamespace(schema_readiness=True),
    )

    def fake_request(method, route, payload=None):
        if method == "POST":
            assert route == "/prompt"
            assert payload["prompt"]["170:161"]["inputs"]["unet_name"] == "model_unet.safetensors"
            observed.append("one_post")
            (directory / "output" / "C4B_DISPOSABLE_QUALIFICATION_00001_.png").write_bytes(
                b"fake-output-created-by-mocked-ComfyUI"
            )
            return {"prompt_id": "test-only-prompt"}
        if route == "/system_stats":
            return {"devices": [{"name": "NVIDIA GeForce", "vram_free": 14 * 1024**3}]}
        if route == "/object_info":
            return {"UNETLoader": {}}
        if route == "/queue":
            return {"queue_running": [], "queue_pending": []}
        raise AssertionError(f"Unexpected request: {route}")

    monkeypatch.setattr(gpu, "_request", fake_request)
    monkeypatch.setattr(
        gpu,
        "_wait_for_one_output",
        lambda *_args, **_kwargs: ("C4B_DISPOSABLE_QUALIFICATION_00001_.png", 12 * 1024**3),
    )
    monkeypatch.setattr(
        gpu,
        "audit_c4b2_external_result",
        lambda *_args, **_kwargs: SimpleNamespace(
            protected_changed_pixels=0,
            editable_changed_pixels=20,
            result_sha256="e" * 64,
            source_sha256="b" * 64,
            mask_sha256="c" * 64,
        ),
    )
    result = gpu.execute_c4b2b_supervised_once(
        directory, **params, operator_confirmed=True, consent_phrase=plan.consent_phrase
    )
    assert observed == ["launched", "one_post", "terminated"]
    assert result["status"] == "GPU_PIXELS_VALIDATED_HUMAN_SEMANTICS_PENDING"
    assert result["protected_changed_pixels"] == 0
    assert not result["candidate_registered"]
    protected_marker = (
        protected / "Canonical Assets" / "STORY-PRO-B00D168E43" / "protected_marker.txt"
    )
    assert protected_marker.read_text() == "unaltered"
    assert (directory / "c4b2b_gpu_result.json").exists()
    with pytest.raises(gpu.C4B2BQualificationError, match="already reserved"):
        gpu.execute_c4b2b_supervised_once(
            directory, **params, operator_confirmed=True, consent_phrase=plan.consent_phrase
        )


def test_c4b2b_ambiguous_boot_failure_is_durable_no_retry(tmp_path, monkeypatch):
    directory, _protected, params = _sandbox(tmp_path, monkeypatch)
    plan = gpu.inspect_c4b2b_execution_plan(directory, **params)
    monkeypatch.setattr(gpu, "_port_unbound", lambda: None)

    class FakeProcess:
        pid = 6789

        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(gpu.subprocess, "Popen", lambda *_a, **_kw: FakeProcess())

    def stop(*_args):
        raise gpu.C4B2BQualificationError("Startup failed after launch")

    monkeypatch.setattr(gpu, "_wait_until_ready", stop)
    with pytest.raises(gpu.C4B2BQualificationError, match="Startup failed"):
        gpu.execute_c4b2b_supervised_once(
            directory, **params, operator_confirmed=True, consent_phrase=plan.consent_phrase
        )
    assert (directory / "c4b2b_execution_reserved.json").exists()
    assert (directory / "c4b2b_execution_failure.json").exists()
    assert not (directory / "c4b2b_gpu_result.json").exists()


def test_c4b2b_reservation_is_atomic_and_exclusive(tmp_path):
    gpu._one_use_path(tmp_path, "claim.json", {"status": "one"})
    with pytest.raises(FileExistsError):
        gpu._one_use_path(tmp_path, "claim.json", {"status": "two"})
    assert json.loads((tmp_path / "claim.json").read_text()) == {"status": "one"}
