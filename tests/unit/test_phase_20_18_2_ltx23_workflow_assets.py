import json
from pathlib import Path


def test_ltx23_workflow_uses_expected_ingredients_lora_path() -> None:
    path = Path(__file__).resolve().parents[2] / "resources" / "workflows" / "workflows" / "ltx23_production_v1_api.json"
    workflow = json.loads(path.read_text(encoding="utf-8"))
    node = workflow["10"]
    assert node["class_type"] == "LTXICLoRALoaderModelOnly"
    assert node["inputs"]["lora_name"] == "LTX-2.3\\ltx-2.3-22b-ic-lora-ingredients-0.9.safetensors"
