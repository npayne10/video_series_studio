"""Read-only, fail-closed CLI for Q3.1.3.5.8d.1 disposable H3 preparation.

Never invokes execute(), authorize_once(), or a ComfyUI POST.
The governed ProductionTask and package must already exist in the disposable VSCS project.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .h3_live_acceptance import H3IsolatedAcceptanceCoordinator, H3IsolatedAcceptanceError
from .minimax_h3_automated_execution import MiniMaxH3AutomatedExecutionService

MARKER = ".vscs_h3_disposable_acceptance"
MARKER_VALUE = "Q3.1.3.5.8"


def initialize_disposable_scope(root: Path) -> Path:
    """Create only a fresh acceptance tree; refuse any pre-existing destination."""
    root = Path(root).expanduser().resolve(strict=False)
    if root.exists():
        raise H3IsolatedAcceptanceError("Refusing to initialize an existing acceptance root")
    root.mkdir(parents=True, exist_ok=False)
    (root / MARKER).write_text(MARKER_VALUE, encoding="utf-8")
    project = root / "project"
    project.mkdir()
    (project / "acceptance-output").mkdir()
    (project / "evidence").mkdir()
    return project


def run_read_only_preflight(
    *,
    acceptance_root: Path,
    task_id: str,
    comfyui_input: Path,
    comfyui_output: Path,
    endpoint: str = "http://127.0.0.1:8188",
) -> dict[str, object]:
    """Compile actual persisted authority without authorizing provider execution."""
    root = Path(acceptance_root).expanduser().resolve(strict=True)
    project = root / "project"
    service = MiniMaxH3AutomatedExecutionService(
        project,
        endpoint=endpoint,
        comfyui_input_directory=comfyui_input,
        comfyui_output_directory=comfyui_output,
    )
    coordinator = H3IsolatedAcceptanceCoordinator(
        service,
        acceptance_root=root,
        project_root=project,
        output_root=project / "acceptance-output",
    )
    prepared = coordinator.prepare(task_id)
    # Inspect native provider counts from the existing actual span compiler.
    package = service._compiled_for_task(prepared.task_id)
    plan = service.plan_compiler.compile(package)
    if len(plan.spans) != 1 or plan.fingerprint != prepared.plan_fingerprint:
        raise H3IsolatedAcceptanceError("H3 preflight changed during frame inspection")
    span = plan.spans[0]
    return {
        "status": "READY_NO_SUBMISSION",
        "project_root": str(prepared.project_root),
        "task_id": prepared.task_id,
        "shot_id": prepared.report.shot_id,
        "plan_fingerprint": prepared.plan_fingerprint,
        "package_fingerprint": prepared.report.package_fingerprint,
        "span_job_id": prepared.report.span_job_ids[0],
        "workflow_fingerprint": prepared.report.workflow_fingerprints[0],
        "model_config_fingerprint": prepared.report.model_config_fingerprints[0],
        "governed_frames": span.governed_frame_count,
        "provider_native_frames": span.provider_frame_count,
        "fps": package.frames_per_second,
        "output_root": str(prepared.output_root),
        "provider_submitted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-submitting isolated H3 readiness")
    parser.add_argument("--acceptance-root", type=Path, required=True)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--init", action="store_true")
    modes.add_argument("--preflight", action="store_true")
    parser.add_argument("--task-id")
    parser.add_argument("--comfyui-input", type=Path)
    parser.add_argument("--comfyui-output", type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8188")
    args = parser.parse_args()
    if args.init:
        project = initialize_disposable_scope(args.acceptance_root)
        print(json.dumps({"status": "SCAFFOLD_CREATED_NOT_READY", "project": str(project)}))
        return 0
    if not args.task_id or not args.comfyui_input or not args.comfyui_output:
        parser.error("--preflight requires --task-id, --comfyui-input, --comfyui-output")
    result = run_read_only_preflight(
        acceptance_root=args.acceptance_root,
        task_id=args.task_id,
        comfyui_input=args.comfyui_input,
        comfyui_output=args.comfyui_output,
        endpoint=args.endpoint,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
