import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = (
    REPOSITORY_ROOT / "resources" / "workflows" / "workflows" / "ltx23_production_v1_api.json"
)


def test_ltx23_workflow_uses_expected_ingredients_lora_path() -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    node = workflow["10"]
    assert node["class_type"] == "LTXICLoRALoaderModelOnly"
    assert node["inputs"]["lora_name"] == "LTX-2.3\\ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors"


def test_ltx23_workflow_chains_three_governed_ingredients_guides() -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    resolver = workflow["108"]
    assert resolver["class_type"] == "VSCSMultiReferenceResolverV721"
    assert resolver["inputs"]["reference_guide_strength"] == ["107", 16]

    primary = workflow["9"]
    secondary = workflow["109"]
    environment = workflow["110"]

    assert primary["inputs"]["image"] == ["108", 0]
    assert primary["inputs"]["strength"] == ["108", 3]
    assert secondary["inputs"]["positive"] == ["9", 0]
    assert secondary["inputs"]["negative"] == ["9", 1]
    assert secondary["inputs"]["latent"] == ["9", 2]
    assert secondary["inputs"]["image"] == ["108", 1]
    assert secondary["inputs"]["strength"] == ["108", 4]
    assert environment["inputs"]["positive"] == ["109", 0]
    assert environment["inputs"]["negative"] == ["109", 1]
    assert environment["inputs"]["latent"] == ["109", 2]
    assert environment["inputs"]["image"] == ["108", 2]
    assert environment["inputs"]["strength"] == ["108", 5]

    assert workflow["37"]["inputs"]["positive"] == ["110", 0]
    assert workflow["37"]["inputs"]["negative"] == ["110", 1]
    assert workflow["23"]["inputs"]["video_latent"] == ["110", 2]
    assert workflow["17"]["inputs"]["positive"] == ["110", 0]
    assert workflow["17"]["inputs"]["negative"] == ["110", 1]


def test_segment_continuity_is_separate_from_governed_reference_guides() -> None:
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    continuity = workflow["103"]

    assert continuity["inputs"]["image"] == ["108", 6]
    assert continuity["inputs"]["bypass"] == ["108", 7]


def test_multi_reference_resolver_is_shipped_as_deployable_custom_node() -> None:
    node_path = (
        REPOSITORY_ROOT
        / "resources"
        / "workflows"
        / "custom_nodes"
        / "vscs_multi_reference_v721.py"
    )
    content = node_path.read_text(encoding="utf-8")

    assert "VSCSMultiReferenceResolverV721" in content
    assert '"provider_multi_reference"' in content
    assert "NODE_CLASS_MAPPINGS" in content
