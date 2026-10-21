"""Read-only Q3.1 audit of H3 benchmark reference/guide conditioning.

Usage:
 python scripts/audit_h3_reference_conditioning.py --workflow-dir D:\\VSCS-H3-Resolution-Benchmark-Ready-v2
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

NODES = ("115", "123", "124", "125", "126", "129", "130", "131", "136", "138", "144")
REFERENCES = ("137", "139", "141", "142", "143")


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]


def audit(workflow_dir: Path) -> dict[str, object]:
    paths = [workflow_dir / f"h3_{suffix}_ready_api.json" for suffix in ("0p2", "0p35")]
    workflows = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    a, b = workflows
    required = (*NODES, *REFERENCES, "145", "92")
    for path, workflow in zip(paths, workflows, strict=True):
        if any(node not in workflow for node in required):
            raise ValueError(f"Required node missing: {path}")
    differences = []
    for node in sorted(set(a) | set(b), key=int):
        if a.get(node) != b.get(node):
            differences.append(
                {
                    "node": node,
                    "class_type": (a.get(node) or b.get(node))["class_type"],
                    "left_inputs": (a.get(node) or {}).get("inputs"),
                    "right_inputs": (b.get(node) or {}).get("inputs"),
                }
            )
    per_run = []
    for path, workflow in zip(paths, workflows, strict=True):
        model = workflow["136"]["inputs"]
        per_run.append(
            {
                "path": str(path),
                "megapixels": workflow["115"]["inputs"]["megapixels"],
                "reference_slots": [
                    {"slot": i, "link": model.get(f"ref_images.ref_image_{i}")}
                    for i in range(5)
                ],
                "guide_image_link": workflow["144"]["inputs"].get("image"),
                "guide_frame": workflow["144"]["inputs"].get("frame_idx"),
                "conditioning_link": workflow["126"]["inputs"].get("conditioning"),
                "guide_node": workflow["144"]["class_type"],
                "frame_length_link": model.get("length"),
                "frame_expression": workflow["131"]["inputs"].get("expression"),
                "seed": workflow["129"]["inputs"].get("noise_seed"),
                "prompt_digest": digest(workflow["138"]["inputs"]["value"]),
                "input_names": {
                    n: workflow[n]["inputs"]["image"] for n in (*REFERENCES, "145")
                },
            }
        )
    return {
        "comparison": per_run,
        "different_nodes": differences,
        "only_resolution_and_output_differ": {
            entry["node"] for entry in differences
        } == {"115", "92"},
        "notes": [
            "Static workflow audit; cannot determine why pixels from reference images appeared in output.",
            "The reference image slots are model inputs, not a temporal guarantee.",
            "Source videos must be reviewed in motion before assigning a root cause.",
            "No ComfyUI job was queued and no media was changed.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.workflow_dir), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
