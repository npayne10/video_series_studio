"""H3 resolution benchmark preparation must never alter production templates."""

import importlib.util
import json
from pathlib import Path

import pytest


def _module():
    path = Path(__file__).resolve().parents[1] / "scripts/prepare_h3_resolution_benchmark.py"
    spec = importlib.util.spec_from_file_location("h3_resolution_benchmark", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_h3_benchmark_variants_are_isolated_and_original_unchanged(tmp_path):
    bench = _module()
    initial = bench.TEMPLATE.read_bytes()
    paths = bench.prepare_variants(tmp_path / "bench")
    assert len(paths) == 5
    assert [json.loads(p.read_text())["115"]["inputs"]["megapixels"] for p in paths] == [
        0.2,
        0.35,
        0.5,
        0.8,
        1.0,
    ]
    for path in paths:
        payload = json.loads(path.read_text())
        assert "VSCS_H3_RES_BENCH_" in payload["92"]["inputs"]["filename_prefix"]
        assert payload["115"]["inputs"]["multiple"] == 32
    assert bench.TEMPLATE.read_bytes() == initial
    with pytest.raises(ValueError, match="empty"):
        bench.prepare_variants(tmp_path / "bench")
