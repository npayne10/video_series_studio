"""Q3.1.3.5.8d.2: seed disposable H3 shot reference assets, never authority.

This operation DOES NOT create or approve a ProductionTask, planning package,
opening keyframe authority, or provider job. Use normal VSCS UI governance.
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

from .h3_live_acceptance import H3IsolatedAcceptanceError

_SCENE = (
    "Stationary futuristic engineering console, precise machined metal surfaces, "
    "one softly illuminated blue diagnostic display, fixed camera, subtle screen "
    "illumination, natural cinematic lighting, realistic materials, no character, "
    "no text overlays, no camera movement."
)


def _png(width: int = 1280, height: int = 720) -> bytes:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    # Deterministic blue-grey synthetic image; does not borrow production IP.
    pixels = (b"\x00" + b"\x20\x30\x40" * width) * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(pixels, level=9))
        + chunk(b"IEND", b"")
    )


def seed_disposable_single_shot(
    *,
    acceptance_root: Path,
    project_directory: Path,
) -> dict[str, str]:
    """Write only an unapproved synthetic reference and operator shot brief."""
    root = Path(acceptance_root).expanduser().resolve(strict=True)
    project = Path(project_directory).expanduser().resolve(strict=True)
    if project == root or not project.is_relative_to(root):
        raise H3IsolatedAcceptanceError("Single-shot seed requires a disposable project")
    marker = root / ".vscs_h3_disposable_acceptance"
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != "Q3.1.3.5.8":
        raise H3IsolatedAcceptanceError("Disposable acceptance marker is missing or invalid")
    if not (project / "project.vscs").is_file() or not (project / "database").is_dir():
        raise H3IsolatedAcceptanceError("A native VSCS project and database are required")
    reference = project / "assets" / "reference" / "h3_acceptance_console.png"
    brief = project / "h3_acceptance_single_shot_brief.json"
    if not reference.parent.is_dir() or reference.exists() or brief.exists():
        raise H3IsolatedAcceptanceError("Acceptance seed assets are missing or already present")
    payload = {
        "schema_version": "1.0",
        "phase": "Q3.1.3.5.8d.2",
        "status": "UNAPPROVED_OPERATOR_BRIEF",
        "scene": _SCENE,
        "reference_path": "assets/reference/h3_acceptance_console.png",
        "target_fps": 24,
        "shot_count": 1,
        "provider": "minimax-h3-ref2va",
        "task_id": None,
        "approved": False,
        "next_action": "Create and approve governed shot, opening authority, package and ProductionTask through VSCS.",
    }
    try:
        with reference.open("xb") as image:
            image.write(_png())
        with brief.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except OSError:
        if not brief.exists():
            reference.unlink(missing_ok=True)
        raise
    return {"reference": str(reference), "brief": str(brief), "status": "SEED_CREATED_NOT_GOVERNED"}


def main() -> int:
    """Explicit operator seed command; no authority or provider mutation."""
    import argparse

    parser = argparse.ArgumentParser(description="Seed one disposable H3 acceptance reference")
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument("--project-directory", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            seed_disposable_single_shot(
                acceptance_root=args.acceptance_root,
                project_directory=args.project_directory,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
