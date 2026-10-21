"""Regression protection for disposable Q3.1.2 Ros reintroduction."""

import importlib.util
import json
from pathlib import Path

import pytest


def test_q312_reintroduces_only_ros_without_overwriting_inputs(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "q312", repo / "scripts/prepare_h3_q3_1_2_ros_reintroduction.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    baseline = json.loads(
        (repo / "resources/workflows/manual/minimax_h3_ref2va_sht002_baseline_api.json").read_text(
            encoding="utf-8"
        )
    )
    baseline["115"]["inputs"]["megapixels"] = 0.35
    for node in ("137", "139", "141", "142", "143", "145"):
        baseline[node]["inputs"]["image"] = (
            f"VSCS_H3_BENCH_{node}_" + baseline[node]["inputs"]["image"]
        )
    reduced = json.loads(json.dumps(baseline))
    reduced.pop("141")
    reduced.pop("143")
    for key in list(reduced["136"]["inputs"]):
        if key.startswith("ref_images.ref_image_"):
            reduced["136"]["inputs"].pop(key)
    for index, node in enumerate(("137", "139", "142")):
        reduced["136"]["inputs"][f"ref_images.ref_image_{index}"] = [node, 0]
    reduced["126"]["inputs"]["conditioning"] = ["144", 0]
    reduced["131"]["inputs"] = {"expression": "56", "values.a": ["132", 0]}
    reduced["92"]["inputs"]["filename_prefix"] = "video/VSCS_H3_Q3_1_0p35_R3"
    source = tmp_path / "r3.json"
    original = tmp_path / "original.json"
    source.write_text(json.dumps(reduced), encoding="utf-8")
    original.write_text(json.dumps(baseline), encoding="utf-8")
    src_bytes = source.read_bytes()
    original_bytes = original.read_bytes()
    destination = tmp_path / "new" / "r4.json"
    module.prepare(source, original, destination)
    result = json.loads(destination.read_text(encoding="utf-8"))
    assert source.read_bytes() == src_bytes
    assert original.read_bytes() == original_bytes
    assert result["141"] == baseline["141"]
    assert "143" not in result
    assert [result["136"]["inputs"][f"ref_images.ref_image_{i}"] for i in range(4)] == [
        ["137", 0],
        ["139", 0],
        ["142", 0],
        ["141", 0],
    ]
    assert "ref_images.ref_image_4" not in result["136"]["inputs"]
    for node in ("115", "125", "126", "129", "130", "131", "136", "144"):
        if node == "136":
            assert result[node]["inputs"]["length"] == reduced[node]["inputs"]["length"]
        else:
            assert result[node] == reduced[node]
    assert result["92"]["inputs"]["filename_prefix"] == module.OUTPUT_PREFIX
    with pytest.raises(FileExistsError):
        module.prepare(source, original, destination)
