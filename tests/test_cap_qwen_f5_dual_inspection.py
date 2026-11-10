"""F5.1 dual-graph inspection retains distinct, read-only findings."""

import json
from types import SimpleNamespace

from vscs.application.caps.qwen_f5_dual_inspection import inspect_dual_workflows
from vscs.application.caps.qwen_f5_preflight import default_workflow_path


def _config(tmp_path):
    path = tmp_path / "xcic_text_api.json"
    path.write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "XCICQueueJobLoader",
                    "inputs": {"queue_file": "queue.json"},
                },
                "2": {"class_type": "EmptySD3LatentImage", "inputs": {"width": 512}},
            }
        ),
        encoding="utf-8",
    )
    return SimpleNamespace(text_workflow_path=path)


def test_dual_inspection_describes_both_graphs_without_provider_calls(tmp_path):
    result = inspect_dual_workflows(_config(tmp_path))
    assert "XCIC queue loaders: 1" in result.legacy_description
    assert result.managed_source_conditioned
    assert result.managed_workflow_sha256
    assert not result.execution_authorized
    output = result.describe()
    assert "LEGACY XCIC" in output
    assert "MANAGED QWEN" in output
    assert "Connected source-image edit graph: YES" in output
    assert "Validated spatial mask/inpainting: NO" in output
    assert "never contacts ComfyUI" in output


def test_missing_managed_graph_does_not_suppress_legacy_information(tmp_path):
    result = inspect_dual_workflows(
        _config(tmp_path), managed_path=tmp_path / "does_not_exist.json"
    )
    assert not result.managed_source_conditioned
    assert result.managed_error is not None
    assert result.managed_workflow_sha256 is None
    assert "LEGACY XCIC" in result.describe()
    assert "Managed workflow invalid" in result.describe()


def test_tampered_managed_source_graph_fail_closed(tmp_path):
    graph = json.loads(default_workflow_path().read_text(encoding="utf-8"))
    graph["170:160"]["inputs"]["image"] = ["171", 2]
    path = tmp_path / "changed_api.json"
    path.write_text(json.dumps(graph), encoding="utf-8")
    result = inspect_dual_workflows(_config(tmp_path), managed_path=path)
    assert not result.managed_source_conditioned
    assert "graph has changed" in str(result.managed_error)


def test_missing_legacy_graph_does_not_block_managed_qwen_inspection(tmp_path):
    config = _config(tmp_path)
    config.text_workflow_path.unlink()
    result = inspect_dual_workflows(config)
    assert result.managed_source_conditioned
    assert result.managed_workflow_sha256
    assert "Cannot read local XCIC workflow" in result.legacy_description
    assert not result.execution_authorized
