"""Q3.1 experiment must not alter baseline workflow or production source."""

import importlib.util
import json
from pathlib import Path

import pytest


def test_prepare_reduced_reference_candidate_is_isolated(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "q31", repo / "scripts/prepare_h3_q3_1_reduced_references.py"
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
    baseline["131"]["inputs"] = {"expression": "56", "values.a": ["132", 0]}
    baseline["126"]["inputs"]["conditioning"] = ["144", 0]
    for node in (*module.KEPT_LOADERS, "145"):
        baseline[node]["inputs"]["image"] = "VSCS_H3_BENCH_" + baseline[node]["inputs"]["image"]
    src = tmp_path / "original.json"
    src.write_text(json.dumps(baseline), encoding="utf-8")
    original = src.read_bytes()
    target = tmp_path / "new" / "candidate.json"
    module.prepare(src, target)
    assert src.read_bytes() == original
    candidate = json.loads(target.read_text(encoding="utf-8"))
    assert all(node not in candidate for node in module.REMOVED_LOADERS)
    assert [candidate["136"]["inputs"][f"ref_images.ref_image_{i}"] for i in range(3)] == [
        ["137", 0],
        ["139", 0],
        ["142", 0],
    ]
    assert "ref_images.ref_image_3" not in candidate["136"]["inputs"]
    assert candidate["115"]["inputs"]["megapixels"] == 0.35
    assert candidate["144"]["inputs"]["frame_idx"] == 0
    with pytest.raises(FileExistsError):
        module.prepare(src, target)
