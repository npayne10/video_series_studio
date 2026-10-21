"""Regression coverage for the Q3.1 read-only workflow audit."""

import importlib.util
import json
from pathlib import Path


def test_h3_reference_conditioning_audit_identifies_only_resolution_and_output(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "h3_audit", repo / "scripts/audit_h3_reference_conditioning.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = json.loads(
        (
            repo / "resources/workflows/manual/minimax_h3_ref2va_sht002_baseline_api.json"
        ).read_text(encoding="utf-8")
    )
    for suffix, mp in (("0p2", 0.2), ("0p35", 0.35)):
        workflow = json.loads(json.dumps(original))
        workflow.pop("146", None)
        workflow.pop("147", None)
        workflow["126"]["inputs"]["conditioning"] = ["144", 0]
        workflow["131"]["inputs"] = {"expression": "56", "values.a": ["132", 0]}
        workflow["115"]["inputs"]["megapixels"] = mp
        workflow["92"]["inputs"]["filename_prefix"] = f"video/VSCS_H3_BENCH_{suffix}"
        (tmp_path / f"h3_{suffix}_ready_api.json").write_text(
            json.dumps(workflow), encoding="utf-8"
        )
    report = module.audit(tmp_path)
    assert report["only_resolution_and_output_differ"] is True
    assert {item["node"] for item in report["different_nodes"]} == {"115", "92"}
    assert report["comparison"][0]["frame_expression"] == "56"
    assert report["comparison"][1]["guide_frame"] == 0
