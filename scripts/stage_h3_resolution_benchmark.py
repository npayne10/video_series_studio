"""Stage an isolated H3 resolution benchmark without submitting any ComfyUI job.

Copies seven historical reference/guide inputs under benchmark-prefixed filenames;
does not edit their original bytes, the VSCS project, or a queued prompt.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

TEMPLATE_NAMES = {
    "137": "CAP-CHR-001-Master-V2.png",
    "139": "CAP-CHR-003 V2.png",
    "141": "CAP-CHR-005 V2.png",
    "142": "CAP-LOC-021_V2_1280x720.png",
    "143": "CAP-PLN-002_V2.png",
    "145": "GBF-36A2A8CA2E4D8452C20765FF.png",
}
MP_VALUES = (0.2, 0.35, 0.5, 0.8, 1.0)
FRAME_COUNT = 56  # H3 length requirement: 17*n + 5.


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage(*, variants: Path, comfy_input: Path, output: Path) -> list[Path]:
    variants = variants.resolve(strict=True)
    comfy_input = comfy_input.resolve(strict=True)
    output = output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output directory must be new or empty")
    for name in TEMPLATE_NAMES.values():
        source = comfy_input / name
        if not source.is_file():
            raise FileNotFoundError(f"Missing reference input: {source}")
    workflows = []
    for mp in MP_VALUES:
        p = variants / f"h3_resolution_{str(mp).replace('.', 'p')}_api.json"
        workflow = json.loads(p.read_text(encoding="utf-8"))
        if workflow["115"]["inputs"]["megapixels"] != mp:
            raise ValueError(f"Unexpected requested resolution: {p}")
        if workflow["136"]["class_type"] != "MiniMaxH3ReferenceToVideo":
            raise ValueError("Unexpected H3 model node")
        if workflow["131"]["class_type"] != "ComfyMathExpression":
            raise ValueError("Unexpected H3 duration node")
        if workflow["92"]["class_type"] != "SaveVideo":
            raise ValueError("Unexpected H3 output node")
        workflows.append((mp, workflow))
    # All safety checks above happen before any files are staged.
    output.mkdir(parents=True, exist_ok=True)
    staged_names = {}
    for node_id, name in TEMPLATE_NAMES.items():
        src = comfy_input / name
        staged = f"VSCS_H3_BENCH_{node_id}_{_sha256(src)[:12]}_{name}"
        dst = comfy_input / staged
        if dst.exists() and _sha256(dst) != _sha256(src):
            raise ValueError(f"Benchmark input collision: {dst}")
        if not dst.exists():
            shutil.copy2(src, dst)
        staged_names[node_id] = staged
    results = []
    for mp, workflow in workflows:
        data = copy.deepcopy(workflow)
        for node_id, staged in staged_names.items():
            data[node_id]["inputs"]["image"] = staged
        # The historical second guide is specifically excluded from test execution.
        data.pop("146", None)
        data.pop("147", None)
        data["126"]["inputs"]["conditioning"] = ["144", 0]
        data["131"]["inputs"] = {
            "expression": str(FRAME_COUNT),
            "values.a": ["132", 0],
        }
        data["138"]["inputs"]["value"] = (
            "Disposable rendering benchmark. Use the five supplied reference pictures "
            "to preserve a consistent photorealistic science-fiction bridge scene. "
            "Show Commander James, Sandra, and Ros with subtle natural movement and "
            "stable identities, on the bridge with Xorix visible. Static camera, one "
            "continuous shot, physically believable materials and lighting; no cuts, "
            "no extra people, no warped faces. Only resolution varies between tests."
        )
        label = str(mp).replace(".", "p")
        data["92"]["inputs"]["filename_prefix"] = f"video/VSCS_H3_BENCH_{label}"
        dest = output / f"h3_{label}_ready_api.json"
        with dest.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        results.append(dest)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", type=Path, required=True)
    parser.add_argument("--comfy-input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for path in stage(variants=args.variants, comfy_input=args.comfy_input, output=args.output):
        print(path)
    print("Prepared ONLY; no ComfyUI generation was queued.")


if __name__ == "__main__":
    main()
