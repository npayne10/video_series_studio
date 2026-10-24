"""Phase 20.19.1 — disposable H3 hold marker and non-mutating status.

Holding is scoped to the acceptance root, not shared provider infrastructure.
The marker blocks the isolated live-run coordinator before token consumption.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .h3_live_acceptance import H3IsolatedAcceptanceError

HOLD_FILE = ".vscs_h3_live_hold.json"
ACCEPTANCE_MARKER = ".vscs_h3_disposable_acceptance"
ACCEPTANCE_VALUE = "Q3.1.3.5.8"


def hold_path(root: Path) -> Path:
    return root / HOLD_FILE


def assert_not_on_hold(root: Path) -> None:
    """Fail closed if this acceptance root is under the review hold."""
    if hold_path(root).exists():
        raise H3IsolatedAcceptanceError(
            "Phase 20.19.1 H3 live-generation hold is active; no live acceptance execution"
        )


def create_hold(acceptance_root: Path, project_directory: Path) -> dict[str, object]:
    """Create immutable hold evidence; never edit production or approve a task."""
    root = acceptance_root.expanduser().resolve(strict=True)
    project = project_directory.expanduser().resolve(strict=True)
    if project == root or not project.is_relative_to(root):
        raise H3IsolatedAcceptanceError("H3 hold project must be inside its disposable root")
    marker = root / ACCEPTANCE_MARKER
    if not marker.is_file() or marker.read_text(encoding="utf-8").strip() != ACCEPTANCE_VALUE:
        raise H3IsolatedAcceptanceError("H3 hold requires a validated disposable marker")
    project_file = project / "project.vscs"
    brief = project / "h3_acceptance_single_shot_brief.json"
    reference = project / "assets" / "reference" / "h3_acceptance_console.png"
    if not (project / "database").is_dir() or not all(
        path.is_file() for path in (project_file, brief, reference)
    ):
        raise H3IsolatedAcceptanceError("H3 hold requires the initialized native seed project")
    if hold_path(root).exists():
        raise H3IsolatedAcceptanceError("H3 hold already exists; refusing overwrite")
    evidence = {
        "phase": "20.19.1",
        "status": "H3_LIVE_GENERATION_ON_HOLD",
        "acceptance_root": str(root),
        "project_directory": str(project),
        "production_task": None,
        "governed_authority": "NOT_ESTABLISHED",
        "provider_submission_authorized": False,
        "resume_requires": "Separate operator approval following Phase 20.19 review",
        "artifacts": {
            str(path.relative_to(project)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (project_file, brief, reference)
        },
    }
    with hold_path(root).open("x", encoding="utf-8") as handle:
        json.dump(evidence, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Place isolated H3 acceptance on audited hold")
    parser.add_argument("--acceptance-root", type=Path, required=True)
    parser.add_argument("--project-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create_hold(args.acceptance_root, args.project_directory), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
