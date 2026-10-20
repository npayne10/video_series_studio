"""Prepare disposable MiniMax H3 API workflow resolution variants; never execute them.

Example:
python scripts/prepare_h3_resolution_benchmark.py --output D:\\VSCS-H3-Resolution-Benchmark
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "resources/workflows/manual/minimax_h3_ref2va_sht002_baseline_api.json"
STEPS = (0.2, 0.35, 0.5, 0.8, 1.0)


def prepare_variants(output: Path, *, template: Path = TEMPLATE) -> list[Path]:
    """Create only new standalone test-only files; never overwrite existing files."""
    source = json.loads(template.read_text(encoding="utf-8"))
    if source["115"]["class_type"] != "ResolutionSelector":
        raise ValueError("Unexpected H3 resolution selector node")
    if source["115"]["inputs"].get("multiple") != 32:
        raise ValueError("Unexpected H3 resolution multiple")
    output = output.resolve()
    if output == REPO or REPO in output.parents:
        raise ValueError("Benchmark output must be outside the VSCS source repository")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Benchmark output directory must be empty to avoid overwrites")
    output.mkdir(parents=True, exist_ok=True)
    destinations: list[Path] = []
    for megapixels in STEPS:
        candidate = copy.deepcopy(source)
        candidate["115"]["inputs"]["megapixels"] = megapixels
        # Distinct output names avoid collisions with governed production jobs.
        candidate["92"]["inputs"]["filename_prefix"] = (
            f"video/VSCS_H3_RES_BENCH_{str(megapixels).replace('.', 'p')}"
        )
        dest = output / f"h3_resolution_{str(megapixels).replace('.', 'p')}_api.json"
        with dest.open("x", encoding="utf-8") as handle:
            json.dump(candidate, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        destinations.append(dest)
    return destinations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in prepare_variants(args.output):
        print(path)


if __name__ == "__main__":
    main()
