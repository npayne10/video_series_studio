"""Prepare a disposable Q3.1 reduced-reference H3 experiment; never submit jobs.

Retains James, Sandra, bridge reference and frame-zero guide. Removes Ros and
standalone Xorix from Ref2VA slots, but does not alter the original source.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

KEPT_LOADERS = ("137", "139", "142")
REMOVED_LOADERS = ("141", "143")
FRAME_COUNT = 56


def prepare(source: Path, destination: Path) -> Path:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination:
        raise ValueError("Source and destination cannot be identical")
    workflow = json.loads(source.read_text(encoding="utf-8"))
    inputs = workflow["136"]["inputs"]
    if workflow["115"]["inputs"]["megapixels"] != 0.35:
        raise ValueError("Q3.1 requires the established 0.35 MP baseline")
    if workflow["130"]["inputs"]["fps"] != 24:
        raise ValueError("Unexpected FPS")
    if workflow["131"]["inputs"] != {
        "expression": str(FRAME_COUNT),
        "values.a": ["132", 0],
    }:
        raise ValueError("Unexpected frame-duration authority")
    if workflow["144"]["inputs"]["frame_idx"] != 0:
        raise ValueError("Expected frame-zero guide")
    if workflow["126"]["inputs"]["conditioning"] != ["144", 0]:
        raise ValueError("Unexpected frame-zero conditioning")
    if [inputs.get(f"ref_images.ref_image_{i}") for i in range(5)] != [
        ["137", 0],
        ["139", 0],
        ["141", 0],
        ["142", 0],
        ["143", 0],
    ]:
        raise ValueError("Original reference order did not match audited baseline")
    if not all(
        workflow[node]["inputs"]["image"].startswith("VSCS_H3_BENCH_")
        for node in (*KEPT_LOADERS, "145")
    ):
        raise ValueError("Source workflow uses non-isolated images")
    candidate = copy.deepcopy(workflow)
    for node in REMOVED_LOADERS:
        candidate.pop(node)
    reference = candidate["136"]["inputs"]
    for key in list(reference):
        if key.startswith("ref_images.ref_image_"):
            del reference[key]
    for i, node in enumerate(KEPT_LOADERS):
        reference[f"ref_images.ref_image_{i}"] = [node, 0]
    candidate["138"]["inputs"]["value"] = (
        "Disposable Q3.1 continuity experiment. Picture 1 is Commander James Spence's "
        "identity reference, Picture 2 is Sandra Crawford's identity reference and "
        "Picture 3 is the Iron Horizon bridge environment. The frame-zero guide "
        "is the starting composition. Maintain one uninterrupted photorealistic "
        "bridge shot with James standing on the left and Sandra seated at the "
        "right control station. Keep the forward planetary view as represented "
        "in the guide, with subtle natural movement. No cuts, no portrait inserts, "
        "no standalone reference images, no additional people. Keep camera static."
    )
    candidate["92"]["inputs"]["filename_prefix"] = "video/VSCS_H3_Q3_1_0p35_R3"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as file:
        json.dump(candidate, file, indent=2, ensure_ascii=False)
        file.write("\n")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(prepare(args.source, args.output))
    print("Prepared only. No ComfyUI job submitted.")


if __name__ == "__main__":
    main()
