from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANUAL = ROOT / "resources" / "workflows" / "manual"


def _load(name: str) -> dict[str, object]:
    return json.loads((MANUAL / name).read_text(encoding="utf-8"))


def _nodes(workflow: dict[str, object], node_type: str) -> list[dict[str, object]]:
    raw = workflow["nodes"]
    assert isinstance(raw, list)
    return [node for node in raw if isinstance(node, dict) and node.get("type") == node_type]


def test_manual_candidate_a_workflow_is_editable_and_package_loader_free() -> None:
    workflow = _load("ltx23_candidate_a_manual_ui_vscs_prompt.json")
    nodes = workflow["nodes"]
    assert isinstance(nodes, list)
    types = [node.get("type") for node in nodes if isinstance(node, dict)]

    assert "VSCSProductionPackageLoaderV720" not in types
    assert "VSCSContinuityPromptV721" not in types
    assert "VSCSMultiReferenceResolverV721" not in types
    assert types.count("CLIPTextEncode") == 2
    assert types.count("LoadImage") == 3
    assert types.count("LTXAddVideoICLoRAGuide") == 3


def test_manual_candidate_a_workflow_preserves_controlled_execution_settings() -> None:
    workflow = _load("ltx23_candidate_a_manual_ui_vscs_prompt.json")

    noise = _nodes(workflow, "RandomNoise")[0]
    assert noise["widgets_values"][0] == 2360325115660865087

    checkpoint = _nodes(workflow, "LowVRAMCheckpointLoader")[0]
    assert checkpoint["widgets_values"][0] == "ltx-2.3-22b-distilled-1.1.safetensors"

    guides = _nodes(workflow, "LTXAddVideoICLoRAGuide")
    assert [guide["widgets_values"][0] for guide in guides] == [-1, -1, -1]

    strengths = [
        node["widgets_values"][0]
        for node in workflow["nodes"]
        if isinstance(node, dict)
        and node.get("type") == "PrimitiveFloat"
        and str(node.get("title", "")).endswith(("0.90", "0.25"))
    ]
    assert strengths == [0.9, 0.25, 0.25]

    ints = {
        str(node.get("title")): node["widgets_values"][0]
        for node in workflow["nodes"]
        if isinstance(node, dict) and node.get("type") == "PrimitiveInt"
    }
    assert ints["Width"] == 1280
    assert ints["Height"] == 720
    assert ints["Provider Frames"] == 145
    assert ints["Governed Output Frames"] == 144


def test_manual_candidate_a_prompt_variants_change_only_prompt_text() -> None:
    current = _load("ltx23_candidate_a_manual_ui_vscs_prompt.json")
    benchmark = _load("ltx23_candidate_a_manual_ui_benchmark_prompt.json")

    current_nodes = current["nodes"]
    benchmark_nodes = benchmark["nodes"]
    assert isinstance(current_nodes, list)
    assert isinstance(benchmark_nodes, list)

    def normalized(nodes: list[object]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for raw in nodes:
            assert isinstance(raw, dict)
            node = dict(raw)
            if node.get("type") == "CLIPTextEncode":
                node["widgets_values"] = ["<PROMPT>"]
            if node.get("type") == "MarkdownNote":
                node["widgets_values"] = ["<NOTE>"]
            result.append(node)
        return result

    assert normalized(current_nodes) == normalized(benchmark_nodes)
    assert current["links"] == benchmark["links"]
