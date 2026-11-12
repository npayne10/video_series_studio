"""F5.4.1C: sealed geometry intent for disposable masked Qwen experiments.

No CAP authority, image generation, or automatic visual approval. The profile
records the exact proposed geometry correction and its review requirements.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from vscs.application.caps.qwen_mask_aware_qualification import (
    MaskAwareQualificationError,
    confirm_preserved_pixels,
)

_PROFILE = "geometry_intent.json"
_EXPERIMENTAL_PROMPT = (
    "EDIT THE MASKED DIAL REGION ONLY. Rebuild the RIGHTMOST rotary control "
    "as a recessed rotary dial mounted BELOW the top surface of the sloping "
    "control shelf. Its circular well must be cut INTO the shelf, with a "
    "visible dark inner cavity, downward sidewall and surrounding flush lip. "
    "The top of the dial must sit at or below the shelf's adjacent surface; "
    "NO raised knob, NO pedestal, NO protruding cylinder and NO surface-mounted "
    "round control. Preserve the same camera angle, graphite material, "
    "lighting, screen, three separate pushbuttons, shelf silhouette, side ribs "
    "and separate workstation. Edit no pixels outside the approved white mask. "
    "The accepted design requires a recessed rotary dial to the right of "
    "three round buttons, not a raised control."
)
_EXPERIMENTAL_NEGATIVE = (
    "raised rotary knob, protruding dial, above-surface control, pedestal, "
    "surface-mounted knob, additional buttons, altered display, warped housing, "
    "text overlays, changed camera angle, duplicate equipment"
)
_REVIEW = (
    "Recessed well visibly below surrounding shelf plane",
    "Dark well interior and visible downward wall rather than raised pedestal",
    "Three separate round buttons remain intact",
    "Dial remains on right side of shelf",
    "No geometry or pixels outside reviewed mask changed",
    "Mask seam and surface continuity inspected",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_geometry_profile(source_sha256: str, mask_sha256: str) -> dict[str, Any]:
    """Deterministic, typed experiment profile: reviewer prose is not executable."""
    return {
        "schema_version": 1,
        "kind": "F541C_RECESSED_ROTARY_DIAL_EXPERIMENT_ONLY",
        "source_sha256": source_sha256,
        "mask_sha256": mask_sha256,
        "positive_prompt": _EXPERIMENTAL_PROMPT,
        "negative_prompt": _EXPERIMENTAL_NEGATIVE,
        "geometry_review_checks": list(_REVIEW),
        "auto_geometry_approval": False,
        "candidate_registration_allowed": False,
        "correction_attempt_allowed": False,
        "gpu_execution_authorized": False,
    }


def verified_geometry_profile(bundle: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Fail closed if any immutable profile content or hash changes."""
    path = bundle / _PROFILE
    if path.is_symlink() or not path.is_file():
        raise MaskAwareQualificationError("F5.4.1C geometry intent evidence missing")
    if _sha(path) != manifest.get("geometry_profile_sha256"):
        raise MaskAwareQualificationError("F5.4.1C geometry intent hash changed")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MaskAwareQualificationError("Geometry intent JSON invalid") from exc
    if value != expected_geometry_profile(
        str(manifest.get("source_sha256")), str(manifest.get("mask_sha256"))
    ):
        raise MaskAwareQualificationError("Geometry intent differs from reviewed contract")
    if manifest.get("geometry_profile_kind") != value["kind"]:
        raise MaskAwareQualificationError("Geometry intent kind changed")
    return value


def prepare_geometry_experiment(
    *,
    project_root: Path,
    source_png: Path,
    bundle_directory: Path,
    bounds: tuple[int, int, int, int],
) -> dict[str, Any]:
    """Create new external B-qualified bundle + sealed geometry intent; no GPU."""
    from vscs.application.caps.qwen_mask_aware_qualification import (
        prepare_mask_aware_bundle,
    )

    # All existing-project and outside-project guards are exercised first.
    report = prepare_mask_aware_bundle(
        source_png=source_png,
        project_root=project_root,
        bundle_directory=bundle_directory,
        bounds=bounds,
    )
    bundle = bundle_directory.resolve(strict=True)
    manifest_path = bundle / "qualification_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = expected_geometry_profile(
        str(manifest["source_sha256"]), str(manifest["mask_sha256"])
    )
    profile_path = bundle / _PROFILE
    if profile_path.exists():
        raise MaskAwareQualificationError("Geometry profile already exists")
    profile_path.write_text(
        json.dumps(profile, sort_keys=True, indent=2), encoding="utf-8"
    )
    manifest["geometry_profile_sha256"] = _sha(profile_path)
    manifest["geometry_profile_kind"] = profile["kind"]
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
    )
    # Close-up is operator review evidence; it is never sent to Qwen.
    with Image.open(bundle / "source.png") as image:
        x0, y0, x1, y1 = bounds
        context = image.convert("RGB").crop(
            (
                max(0, x0 - 90),
                max(0, y0 - 75),
                min(image.width, x1 + 90),
                min(image.height, y1 + 75),
            )
        )
    context.save(bundle / "geometry_context_preview.png")
    manifest["geometry_context_preview_sha256"] = _sha(
        bundle / "geometry_context_preview.png"
    )
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2), encoding="utf-8"
    )
    verified_geometry_profile(bundle, manifest)
    return {
        "status": "F541C_GEOMETRY_PREPARED_NO_GPU",
        "bundle_directory": str(bundle),
        "source_sha256": manifest["source_sha256"],
        "mask_sha256": manifest["mask_sha256"],
        "mask_bounds": list(report.mask_bounds),
        "geometry_profile_sha256": manifest["geometry_profile_sha256"],
        "geometry_context_preview_sha256": manifest["geometry_context_preview_sha256"],
        "gpu_submitted": False,
        "execution_authorized": False,
        "governed_attempt_consumed": False,
    }


def audit_geometry_experiment(
    *, bundle_directory: Path, output_png: Path
) -> dict[str, Any]:
    """Quantify inside/outside changes. Human judgment required for actual recess."""
    bundle = bundle_directory.resolve(strict=True)
    manifest = json.loads(
        (bundle / "qualification_manifest.json").read_text(encoding="utf-8")
    )
    profile = verified_geometry_profile(bundle, manifest)
    source = bundle / "source.png"
    mask_path = bundle / "mask.png"
    if (
        source.is_symlink()
        or mask_path.is_symlink()
        or _sha(source) != manifest.get("source_sha256")
        or _sha(mask_path) != manifest.get("mask_sha256")
        or _sha(bundle / "geometry_context_preview.png")
        != manifest.get("geometry_context_preview_sha256")
    ):
        raise MaskAwareQualificationError("Geometry source, mask or context evidence changed")
    evidence = confirm_preserved_pixels(source, output_png, mask_path)
    with (
        Image.open(source) as a,
        Image.open(output_png) as b,
        Image.open(mask_path) as mask,
    ):
        changed = ImageChops.difference(a.convert("RGB"), b.convert("RGB"))
        union = ImageChops.lighter(
            ImageChops.lighter(changed.getchannel(0), changed.getchannel(1)),
            changed.getchannel(2),
        )
        edited = ImageChops.multiply(union.point(lambda v: 255 if v else 0), mask)
        changed_inside = edited.histogram()[255]
        inside = mask.histogram()[255]
    return {
        **evidence,
        "status": (
            "PIXEL_PRESERVED_GEOMETRY_REVIEW_REQUIRED"
            if evidence["outside_mask_pixels_identical"] and changed_inside > 0
            else "GEOMETRY_EXPERIMENT_REQUIRES_INVESTIGATION"
        ),
        "changed_pixels_inside_mask": changed_inside,
        "inside_change_percentage": round(100.0 * changed_inside / inside, 4),
        "recessed_dial_verified": None,
        "human_review_checks": profile["geometry_review_checks"],
        "correction_attempt_consumed": False,
        "canon_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="F5.4.1C offline recessed-dial geometry experiment"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--audit", action="store_true")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--roi", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM")
    )
    args = parser.parse_args()
    try:
        if args.prepare:
            if args.project_root is None or args.source is None or args.roi is None:
                raise MaskAwareQualificationError(
                    "Offline preparation requires project, source and four ROI coordinates"
                )
            result = prepare_geometry_experiment(
                project_root=args.project_root,
                source_png=args.source,
                bundle_directory=args.bundle,
                bounds=(args.roi[0], args.roi[1], args.roi[2], args.roi[3]),
            )
        else:
            if args.output is None:
                raise MaskAwareQualificationError("Audit requires a generated output PNG")
            result = audit_geometry_experiment(
                bundle_directory=args.bundle, output_png=args.output
            )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
