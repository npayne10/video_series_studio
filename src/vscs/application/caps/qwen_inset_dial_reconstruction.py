"""F5.4.1D: prepare a single cavity-to-inset-dial experiment outside CAP.

Takes only the completed F5.4.1C isolated output as input. A new, smaller mask
must be reviewed. Preparation never submits work to ComfyUI.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image

from vscs.application.caps.geometry_correction_policy import (
    GeometryDefect,
    prepare_repair_plan,
    write_repair_plan_once,
)
from vscs.application.caps.qwen_f53_isolated_acceptance import _ensure_external
from vscs.application.caps.qwen_mask_aware_qualification import (
    MaskAwareQualificationError,
    build_experimental_masked_graph,
    create_binary_edit_mask,
    validate_experimental_graph,
)
from vscs.application.caps.qwen_f5_preflight import default_workflow_path

_PROMPT = (
    "EDIT THE MASKED CIRCULAR CAVITY ONLY. INSERT ONE LOW-PROFILE ROTARY "
    "DIAL INSIDE THE EXISTING RECESSED WELL on the right side of the shelf. "
    "The well's outer flush lip and visible downward inner wall MUST remain. "
    "The new dial is a small matte-graphite circular control with a subtly "
    "grooved rim and a narrow indicator mark; its entire top face MUST remain "
    "BELOW the surrounding sloping shelf plane. Preserve the original cavity "
    "boundary, perspective, lighting and shading. The existing three buttons, "
    "display, housing and separate workstation must remain unchanged. "
    "Do not produce an empty hole or a knob sticking out above the shelf."
)
_NEGATIVE = (
    "empty circular hole, no dial, filled-over well, surface-mounted knob, "
    "raised knob, pedestal, protruding control, duplicate dial, fourth button, "
    "changed shelf, changed workstation, changed camera angle"
)
_INTENT = "inset_dial_intent.json"
_KIND = "F541D_ONE_SHOT_INSET_DIAL_RECONSTRUCTION"
_PREVIOUS = "run_003"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise MaskAwareQualificationError("Missing or symlinked isolated lineage evidence")
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MaskAwareQualificationError("Invalid lineage JSON evidence") from exc
    if not isinstance(data, dict) or not all(isinstance(key, str) for key in data):
        raise MaskAwareQualificationError("Lineage evidence must be a JSON object")
    return dict(data)


def verified_previous_cavity(previous: Path, project_root: Path) -> dict[str, Any]:
    """Require completed, unchanged run_003 without touching its files."""
    parent, project = _ensure_external(previous, project_root)
    if parent.name != _PREVIOUS or parent.is_symlink() or not parent.is_dir():
        raise MaskAwareQualificationError("Expected completed external run_003")
    if any(item.is_symlink() for item in parent.iterdir()):
        raise MaskAwareQualificationError("Previous bundle contains a symlink")
    manifest = _json(parent / "qualification_manifest.json")
    result = _json(parent / "qualification_result.json")
    source = parent / "masked_qwen_output.png"
    if (
        manifest.get("bundle_directory") != str(parent)
        or manifest.get("project_root") != str(project)
        or manifest.get("geometry_profile_kind")
        != "F541C_RECESSED_ROTARY_DIAL_EXPERIMENT_ONLY"
        or result.get("status") != "SPATIAL_PIXEL_PRESERVATION_VERIFIED"
        or result.get("outside_mask_pixels_identical") is not True
        or result.get("protected_changed_pixels") != 0
        or result.get("candidate_registered") is not False
        or result.get("correction_attempt_consumed") is not False
        or not (parent / "execution_reserved.json").is_file()
        or not source.is_file()
        or source.is_symlink()
        or _digest(source) != result.get("output_sha256")
        or _digest(parent / "source.png") != manifest.get("source_sha256")
        or _digest(parent / "mask.png") != manifest.get("mask_sha256")
        or _digest(parent / "experimental_masked_api.json")
        != manifest.get("experimental_graph_sha256")
    ):
        raise MaskAwareQualificationError("Previous cavity result is incomplete or changed")
    audit = result.get("geometry_audit")
    if not isinstance(audit, dict) or audit.get("outside_mask_pixels_identical") is not True:
        raise MaskAwareQualificationError("Previous geometry audit not verified")
    previous_bounds = manifest.get("mask_bounds")
    if (
        not isinstance(previous_bounds, list)
        or len(previous_bounds) != 4
        or any(type(x) is not int for x in previous_bounds)
    ):
        raise MaskAwareQualificationError("Previous cavity ROI evidence invalid")
    return {
        "parent_bundle": str(parent),
        "previous_bounds": previous_bounds,
        "parent_result_sha256": _digest(parent / "qualification_result.json"),
        "parent_source_sha256": manifest["source_sha256"],
        "source_path": str(source),
        "source_sha256": _digest(source),
    }


def expected_reconstruction_intent(source_sha256: str, mask_sha256: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": _KIND,
        "source_sha256": source_sha256,
        "mask_sha256": mask_sha256,
        "positive_prompt": _PROMPT,
        "negative_prompt": _NEGATIVE,
        "candidate_registration_allowed": False,
        "governed_attempt_allowed": False,
        "gpu_execution_authorized": False,
        "human_geometry_verification_required": True,
    }


def verified_reconstruction_intent(bundle: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    path = bundle / _INTENT
    value = _json(path)
    if _digest(path) != manifest.get("reconstruction_intent_sha256"):
        raise MaskAwareQualificationError("Reconstruction intent hash mismatch")
    if value != expected_reconstruction_intent(
        str(manifest.get("source_sha256")), str(manifest.get("mask_sha256"))
    ):
        raise MaskAwareQualificationError("Reconstruction intent differs from reviewed contract")
    return value


def prepare_reconstruction(
    *,
    project_root: Path,
    previous_bundle: Path,
    new_bundle: Path,
    bounds: tuple[int, int, int, int],
) -> dict[str, Any]:
    """Create exclusive external run_004; no modifications to run_003 or CAP."""
    previous = verified_previous_cavity(previous_bundle, project_root)
    target, project = _ensure_external(new_bundle, project_root)
    if (
        target.is_symlink()
        or target.exists()
        or target.name != "run_004"
        or target.parent != Path(previous["parent_bundle"]).parent
    ):
        raise MaskAwareQualificationError("New run_004 must be absent beside run_003")
    source_path = Path(previous["source_path"])
    x0, y0, x1, y1 = bounds
    px0, py0, px1, py1 = previous["previous_bounds"]
    if (
        any(type(v) is not int for v in bounds)
        or not px0 <= x0 < x1 <= px1
        or not py0 <= y0 < y1 <= py1
        or (x1 - x0) * (y1 - y0) > (px1 - px0) * (py1 - py0) // 2
    ):
        raise MaskAwareQualificationError(
            "New reconstruction ROI must stay within half of the previously approved cavity ROI"
        )
    graph = build_experimental_masked_graph()
    validate_experimental_graph(graph)
    target.mkdir(parents=True, exist_ok=False)
    source = target / "source.png"
    source.write_bytes(source_path.read_bytes())
    mask = target / "mask.png"
    report = create_binary_edit_mask(source, mask, bounds)
    with Image.open(source) as image:
        original = image.convert("RGBA")
    tint = Image.new("RGBA", original.size, (255, 0, 0, 0))
    tint.paste((255, 0, 0, 110), bounds)
    Image.alpha_composite(original, tint).convert("RGB").save(target / "roi_preview.png")
    graph_path = target / "experimental_masked_api.json"
    graph_path.write_text(json.dumps(graph, sort_keys=True, indent=2), encoding="utf-8")
    intent = expected_reconstruction_intent(_digest(source), _digest(mask))
    intent_path = target / _INTENT
    intent_path.write_text(json.dumps(intent, sort_keys=True, indent=2), encoding="utf-8")
    plan = prepare_repair_plan(
        defect=GeometryDefect.MISSING_COMPONENT,
        asset_kind="diagnostic_console",
        asset_id="STORY-PRO-B00D168E43",
        reviewed_requirement="Recessed rotary dial seated below the sloping shelf plane",
        observed_failure="Existing cavity is empty; dial must be installed inside it",
        source_sha256=_digest(source),
        mask_sha256=_digest(mask),
        source_lineage=str(previous["parent_bundle"]),
    )
    plan_hash = write_repair_plan_once(target / "geometry_repair_plan.json", plan)
    manifest = {
        "schema_version": 1,
        "kind": "F541B_OFFLINE_EXPERIMENTAL_MASK_NOT_EXECUTABLE",
        "project_root": str(project),
        "bundle_directory": str(target),
        "original_source_path": str(source_path),
        "original_source_sha256": previous["source_sha256"],
        "source_sha256": _digest(source),
        "mask_sha256": _digest(mask),
        "mask_bounds": list(report.mask_bounds),
        "mask_coverage_percent": report.mask_coverage_percent,
        "roi_preview_sha256": _digest(target / "roi_preview.png"),
        "template_sha256": _digest(default_workflow_path()),
        "experimental_graph_sha256": _digest(graph_path),
        "mask_input_filename": graph["F541B_MASK"]["inputs"]["image"],
        "reconstruction_intent_sha256": _digest(intent_path),
        "repair_plan_sha256": plan_hash,
        "parent_bundle": previous["parent_bundle"],
        "parent_result_sha256": previous["parent_result_sha256"],
        "parent_source_sha256": previous["parent_source_sha256"],
        "candidate_registration_allowed": False,
        "correction_attempt_reserved": False,
        "gpu_execution_authorized": False,
        "geometry_profile_kind": _KIND,
    }
    (target / "qualification_manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
    )
    return {
        "status": "F541D_RECONSTRUCTION_PREPARED_NO_GPU",
        "bundle_directory": str(target),
        "source_sha256": manifest["source_sha256"],
        "mask_sha256": manifest["mask_sha256"],
        "mask_bounds": manifest["mask_bounds"],
        "reconstruction_intent_sha256": manifest["reconstruction_intent_sha256"],
        "repair_plan_sha256": plan_hash,
        "gpu_submitted": False,
        "governed_attempt_consumed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="F5.4.1D offline inset dial reconstruction")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--previous-bundle", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--roi", type=int, nargs=4, required=True)
    args = parser.parse_args()
    try:
        result = prepare_reconstruction(
            project_root=args.project_root,
            previous_bundle=args.previous_bundle,
            new_bundle=args.bundle,
            bounds=(args.roi[0], args.roi[1], args.roi[2], args.roi[3]),
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
