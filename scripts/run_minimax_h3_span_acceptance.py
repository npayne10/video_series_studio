"""Run exactly one governed MiniMax H3 span for controlled functional acceptance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from vscs.application.production_tasks import ProductionTaskType
from vscs.infrastructure.production import JsonProductionTaskRepository
from vscs.infrastructure.production_execution import (
    FFmpegMiniMaxH3SpanNormalizer,
    LiveMiniMaxH3ComfyUISpanProvider,
    MiniMaxH3ComfyUIWorkflowCompiler,
    MiniMaxH3SpanAdapterCompiler,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationService,
)


SHT002 = "EP-001-SCN-001-SHT-002"
SHT002_OPENING_SHA256 = "c4b083314cb06b7c6884029827cd9c3eb1d784bea7f7d9f5fbddcb4e32abd3ef"
FORBIDDEN_SPAN1_ALIASES = ("ros", "rohsgard", "cap-chr-005")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _task(project: Path, shot_id: str):
    repository = JsonProductionTaskRepository(project / "production" / "scheduling" / "tasks")
    matches = tuple(
        task
        for task in repository.list_all()
        if (task.shot_id or "").strip().upper() == shot_id
        and task.task_type is ProductionTaskType.VIDEO_GENERATION
    )
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one VIDEO_GENERATION ProductionTask for {shot_id}; found {len(matches)}"
        )
    return matches[0]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--shot-id", default=SHT002)
    parser.add_argument("--sequence", type=int, default=1)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8188")
    parser.add_argument("--comfyui-root", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    project = args.project.expanduser().resolve(strict=False)
    comfyui_root = args.comfyui_root.expanduser().resolve(strict=False)
    input_directory = comfyui_root / "ComfyUI" / "input"
    output_directory = comfyui_root / "ComfyUI" / "output"
    shot_id = args.shot_id.strip().upper()

    if not project.is_dir():
        raise RuntimeError(f"VSCS project does not exist: {project}")
    if not input_directory.is_dir() or not output_directory.is_dir():
        raise RuntimeError(
            "ComfyUI input/output directories were not found below the supplied portable root"
        )

    task = _task(project, shot_id)
    compiled = LocalProductionPackageCompilationService(project).compile_current(task)
    execution = MiniMaxH3SpanAdapterCompiler(project).compile_execution(
        compiled,
        sequence_number=args.sequence,
    )

    if execution.sequence_number == 1 and shot_id == SHT002:
        observed = execution.guide_image_sha256.lower()
        if observed != SHT002_OPENING_SHA256:
            raise RuntimeError(
                "SHT-002 opening guide checksum does not match governed boundary authority: "
                f"{observed}"
            )

    workflow_compiler = MiniMaxH3ComfyUIWorkflowCompiler(
        project,
        comfyui_input_directory=input_directory,
    )
    provider_job = workflow_compiler.compile(execution)
    serialized = json.dumps(provider_job.workflow, sort_keys=True).casefold()

    if execution.sequence_number == 1:
        leaked = tuple(alias for alias in FORBIDDEN_SPAN1_ALIASES if alias in serialized)
        if leaked:
            raise RuntimeError(
                "SPAN-001 provider payload leaked future Ros authority: " + ", ".join(leaked)
            )

    print("H3 SINGLE-SPAN PREFLIGHT PASS")
    print(f"Shot: {compiled.shot_id}")
    print(f"Task: {compiled.task_id}")
    print(f"Span: {execution.span_id} / sequence {execution.sequence_number}")
    print(
        f"Frames: provider={execution.provider_frame_count}, "
        f"governed={execution.governed_frame_count}"
    )
    print(f"Guide: {execution.guide_image_path}")
    print(f"Guide SHA256: {execution.guide_image_sha256}")
    print("References:")
    for slot in execution.reference_slots:
        print(
            f"  {slot.picture_tag}: {slot.asset_id} / {slot.reference_id} / {slot.source_path}"
        )
    print(f"Workflow fingerprint: {provider_job.workflow_fingerprint}")
    print(f"Model/config fingerprint: {provider_job.model_config_fingerprint}")

    if not args.execute:
        print("PREVIEW ONLY — no ComfyUI job submitted.")
        return 0

    provider = LiveMiniMaxH3ComfyUISpanProvider(
        project,
        endpoint=args.endpoint,
        comfyui_input_directory=input_directory,
        comfyui_output_directory=output_directory,
    )
    health = provider.client.health()
    if not health.healthy:
        raise RuntimeError("ComfyUI health preflight failed")

    try:
        raw_output = provider.render(execution)
        acceptance_root = (
            project
            / ".vscs"
            / "h3_span_acceptance"
            / compiled.task_id
            / execution.job_id
        )
        normalized_output = FFmpegMiniMaxH3SpanNormalizer(project).normalize(
            raw_output,
            acceptance_root / f"span-{execution.sequence_number:03d}-normalized.mp4",
            provider_frame_count=execution.provider_frame_count,
            governed_frame_count=execution.governed_frame_count,
            frames_per_second=compiled.frames_per_second,
        )
    finally:
        provider.free_models_and_memory()

    acceptance_root.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": "1.0",
        "phase": "20.18.2.3.6.4e.2",
        "shot_id": compiled.shot_id,
        "task_id": compiled.task_id,
        "span_id": execution.span_id,
        "sequence_number": execution.sequence_number,
        "job_id": execution.job_id,
        "provider_frame_count": execution.provider_frame_count,
        "governed_frame_count": execution.governed_frame_count,
        "guide_image_path": execution.guide_image_path,
        "guide_image_sha256": execution.guide_image_sha256,
        "reference_slot_fingerprint": execution.reference_slot_fingerprint,
        "prompt_fingerprint": execution.prompt_fingerprint,
        "workflow_fingerprint": provider_job.workflow_fingerprint,
        "model_config_fingerprint": provider_job.model_config_fingerprint,
        "raw_output_path": str(raw_output),
        "raw_output_sha256": _sha256(raw_output),
        "normalized_output_path": str(normalized_output),
        "normalized_output_sha256": _sha256(normalized_output),
        "visual_acceptance": "pending",
    }
    evidence_path = acceptance_root / "span_acceptance.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print("H3 SPAN EXECUTION COMPLETE")
    print(f"Raw output: {raw_output}")
    print(f"Normalized output: {normalized_output}")
    print(f"Evidence: {evidence_path}")
    print("Visual acceptance remains PENDING.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
