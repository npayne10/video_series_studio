"""Prepare Q3.1.2 Ros-reference reintroduction; no ComfyUI submission.

Builds a new four-reference disposable workflow from the successful Q3.1
three-reference candidate and the original five-reference benchmark.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

OUTPUT_PREFIX = "video/VSCS_H3_Q3_1_2_0p35_R4"
REFERENCE_IDS = ("137", "139", "142", "141")


def prepare(source: Path, original: Path, destination: Path) -> Path:
    source = source.resolve(strict=True)
    original = original.resolve(strict=True)
    destination = destination.resolve()
    if destination in (source, original):
        raise ValueError("Destination must be different from both sources")
    candidate = json.loads(source.read_text(encoding="utf-8"))
    baseline = json.loads(original.read_text(encoding="utf-8"))
    if candidate["92"]["inputs"]["filename_prefix"] != "video/VSCS_H3_Q3_1_0p35_R3":
        raise ValueError("Source is not the successful Q3.1 R3 configuration")
    if candidate["115"]["inputs"]["megapixels"] != 0.35:
        raise ValueError("Unexpected resolution")
    if candidate["130"]["inputs"]["fps"] != 24:
        raise ValueError("Unexpected FPS")
    if candidate["131"]["inputs"] != {"expression": "56", "values.a": ["132", 0]}:
        raise ValueError("Unexpected duration expression")
    if candidate["144"]["inputs"]["frame_idx"] != 0:
        raise ValueError("Frame-zero guide must remain in place")
    if candidate["126"]["inputs"]["conditioning"] != ["144", 0]:
        raise ValueError("Guide conditioning mismatch")
    if candidate["129"]["inputs"]["noise_seed"] != 123456:
        raise ValueError("Unexpected seed")
    slots = candidate["136"]["inputs"]
    if [slots.get(f"ref_images.ref_image_{i}") for i in range(3)] != [
        ["137", 0], ["139", 0], ["142", 0]
    ]:
        raise ValueError("Unexpected three-reference configuration")
    if any(key.startswith("ref_images.ref_image_") and key not in {
        "ref_images.ref_image_0",
        "ref_images.ref_image_1",
        "ref_images.ref_image_2",
    } for key in slots):
        raise ValueError("Unexpected additional reference slots")
    if "141" in candidate or "143" in candidate:
        raise ValueError("Reduced-reference candidate contains excluded loaders")
    if baseline["136"]["inputs"].get("ref_images.ref_image_2") != ["141", 0]:
        raise ValueError("Original Ros slot does not match benchmark")
    ros = baseline["141"]
    if ros["class_type"] != "LoadImage" or not ros["inputs"]["image"].startswith(
        "VSCS_H3_BENCH_141_"
    ):
        raise ValueError("Ros reference must use the isolated benchmark input")
    if any(
        not candidate[node]["inputs"]["image"].startswith("VSCS_H3_BENCH_")
        for node in ("137", "139", "142", "145")
    ):
        raise ValueError("Unexpected unisolated reference image")
    result = copy.deepcopy(candidate)
    result["141"] = copy.deepcopy(ros)
    result["136"]["inputs"]["ref_images.ref_image_3"] = ["141", 0]
    result["138"]["inputs"]["value"] = (
        "Disposable Q3.1.2 bridge continuity experiment. References identify "
        "Commander James Spence, Sandra Crawford, the Iron Horizon bridge, and "
        "Major Ros Rohsgard respectively. The frame-zero guide establishes the "
        "bridge composition: James stands on the left and Sandra is seated at "
        "the right console, with Xorix visible through the forward window. "
        "Maintain one continuous photorealistic bridge shot, with subtle "
        "natural motion and a static camera. Ros may enter the background "
        "from off-screen later in the shot without displacing the other "
        "characters. No cuts, portrait inserts, standalone reference frames, "
        "or scene transitions."
    )
    result["92"]["inputs"]["filename_prefix"] = OUTPUT_PREFIX
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2, ensure_ascii=False)
        file.write("\n")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(prepare(args.source, args.original, args.output))
    print("Prepared only. No ComfyUI generation was submitted.")


if __name__ == "__main__":
    main()
