from pathlib import Path

from vscs.infrastructure.production_execution.package_compilation import ComfyUIV714InputAssurance


def test_committed_comfyui_workflow_consumes_compiled_production_inputs() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    workflow = (
        repository_root
        / "resources"
        / "workflows"
        / "workflows"
        / "video_production_engine_v7_1_4_api.json"
    )

    report = ComfyUIV714InputAssurance().inspect(workflow)

    assert report.passed is True, report.issues
    traced = {trace.name for trace in report.traces}
    assert {
        "target_description",
        "shot_prompt",
        "negative_prompt",
        "previous_approved_final_frame",
        "filename_prefix",
        "width",
        "height",
        "frame_count",
        "seed",
        "fps",
        "cfg",
        "ic_lora_strength",
        "composition_plan",
    } <= traced
