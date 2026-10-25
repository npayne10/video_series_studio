"""Phase 20.19.3 — non-mutating disposable Story-to-Task scope check.

Never creates a project, writes planning records, removes the H3 hold,
or communicates with a video provider.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


class GoldenPathScopeError(RuntimeError):
    """The requested golden-path audit would compromise project isolation."""


def inspect_golden_path_scope(
    *,
    audit_project: Path,
    h3_acceptance_root: Path,
    prohibited_project_roots: tuple[Path, ...],
) -> dict[str, object]:
    """Require a genuine native audit project outside all protected roots."""
    project = audit_project.expanduser().resolve(strict=True)
    h3_root = h3_acceptance_root.expanduser().resolve(strict=True)
    if not project.is_dir() or not (project / "project.vscs").is_file():
        raise GoldenPathScopeError("Audit project must be a native VSCS project")
    if not (project / "database").is_dir():
        raise GoldenPathScopeError("Audit project is missing its native database directory")
    if project == h3_root or project.is_relative_to(h3_root):
        raise GoldenPathScopeError("Audit project must not be inside H3 acceptance scope")
    for protected in prohibited_project_roots:
        protected_root = protected.expanduser().resolve(strict=False)
        if project == protected_root or project.is_relative_to(protected_root):
            raise GoldenPathScopeError("Audit project overlaps a protected production project")
    hold = h3_root / ".vscs_h3_live_hold.json"
    if not hold.is_file():
        raise GoldenPathScopeError("H3 hold evidence missing; golden path is blocked")
    try:
        manifest = json.loads(hold.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GoldenPathScopeError("H3 hold evidence cannot be read") from exc
    if (
        manifest.get("status") != "H3_LIVE_GENERATION_ON_HOLD"
        or manifest.get("provider_submission_authorized") is not False
    ):
        raise GoldenPathScopeError("H3 live generation is not confirmed on hold")
    return {
        "phase": "20.19.3",
        "status": "ISOLATED_NATIVE_PROJECT_READY_FOR_UI_TRACE",
        "audit_project": str(project),
        "h3_hold_verified": True,
        "provider_submitted": False,
        "governed_task_created": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only VSCS golden-path safety gate")
    parser.add_argument("--audit-project", type=Path, required=True)
    parser.add_argument("--h3-acceptance-root", type=Path, required=True)
    parser.add_argument("--protect", type=Path, action="append", default=[])
    args = parser.parse_args()
    print(
        json.dumps(
            inspect_golden_path_scope(
                audit_project=args.audit_project,
                h3_acceptance_root=args.h3_acceptance_root,
                prohibited_project_roots=tuple(args.protect),
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
