"""F5 read-only hardware preflight tests: no provider submission or CAP writes."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from vscs.application.caps import qwen_f5_preflight as preflight


def _fake_provider():
    return SimpleNamespace(
        healthcheck=Mock(),
        validate_nodes=Mock(),
        object_info=Mock(return_value={}),
        submit=Mock(),
    )


def test_f5_reports_preflight_ready_without_gpu_inference(monkeypatch):
    provider = _fake_provider()
    monkeypatch.setattr(preflight, "validate_managed_qwen_model_choices", Mock())
    monkeypatch.setattr(
        preflight,
        "_gpu_inventory",
        lambda: (
            (
                {
                    "name": "NVIDIA GeForce RTX 5060 Ti",
                    "memory_total_mib": "16303",
                    "memory_free_mib": "15000",
                    "driver_version": "600.00",
                },
            ),
            None,
        ),
    )
    result = preflight.inspect_qwen_f5_hardware(client=provider)
    assert result.status == "PREFLIGHT_READY_NO_GPU_INFERENCE"
    assert result.graph_sha256
    assert result.comfyui_reachable
    assert result.nodes_and_models_available
    assert not result.execution_authorized
    provider.submit.assert_not_called()
    provider.healthcheck.assert_called_once()
    provider.validate_nodes.assert_called_once()


def test_f5_missing_installed_models_fail_closed(monkeypatch):
    provider = _fake_provider()
    monkeypatch.setattr(
        preflight,
        "validate_managed_qwen_model_choices",
        Mock(side_effect=RuntimeError("Model is not advertised")),
    )
    monkeypatch.setattr(preflight, "_gpu_inventory", lambda: ((), None))
    result = preflight.inspect_qwen_f5_hardware(client=provider)
    assert result.status == "BLOCKED"
    assert result.comfyui_reachable
    assert not result.nodes_and_models_available
    assert "Model is not advertised" in result.errors[0]
    provider.submit.assert_not_called()


def test_f5_unreachable_comfyui_fail_closed(monkeypatch):
    provider = _fake_provider()
    provider.healthcheck.side_effect = RuntimeError("ComfyUI is offline")
    monkeypatch.setattr(preflight, "_gpu_inventory", lambda: ((), "nvidia-smi unavailable"))
    result = preflight.inspect_qwen_f5_hardware(client=provider)
    assert result.status == "BLOCKED"
    assert not result.comfyui_reachable
    assert len(result.errors) == 2
    provider.submit.assert_not_called()


def test_f5_missing_workflow_fail_closed(tmp_path, monkeypatch):
    provider = _fake_provider()
    monkeypatch.setattr(preflight, "_gpu_inventory", lambda: ((), None))
    result = preflight.inspect_qwen_f5_hardware(
        workflow_path=tmp_path / "not-found.json", client=provider
    )
    assert result.status == "BLOCKED"
    assert not result.graph_sha256
    provider.validate_nodes.assert_not_called()
    provider.submit.assert_not_called()


def test_f5_rejects_remote_endpoint_before_any_network():
    with pytest.raises(RuntimeError, match="loopback"):
        preflight.inspect_qwen_f5_hardware(comfyui_url="http://192.168.1.100:8188")


def test_f5_parses_gpu_snapshot(monkeypatch):
    completed = SimpleNamespace(
        returncode=0,
        stdout="NVIDIA GeForce RTX 5060 Ti, 16303, 14955, 591.00\n",
        stderr="",
    )
    run = Mock(return_value=completed)
    monkeypatch.setattr(preflight.subprocess, "run", run)
    inventory, error = preflight._gpu_inventory()
    assert error is None
    assert len(inventory) == 1
    assert inventory[0]["memory_free_mib"] == "14955"
    assert run.call_args.kwargs["timeout"] == 10


def test_f5_missing_nvidia_smi_is_non_authorizing(monkeypatch):
    monkeypatch.setattr(
        preflight.subprocess,
        "run",
        Mock(side_effect=FileNotFoundError("nvidia-smi unavailable")),
    )
    inventory, error = preflight._gpu_inventory()
    assert inventory == ()
    assert error is not None


def test_f5_default_graph_is_present():
    assert isinstance(preflight.default_workflow_path(), Path)
    assert preflight.default_workflow_path().is_file()
