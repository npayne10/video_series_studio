from __future__ import annotations

import json
from pathlib import Path

from vscs.application.production_execution.span_scoped_provider_inputs import SpanReferenceSlot
from vscs.infrastructure.production_execution import (
    LiveMiniMaxH3ComfyUISpanProvider,
    MiniMaxH3ComfyUIWorkflowCompiler,
    MiniMaxH3SpanExecution,
)


def _workflow() -> dict[str, object]:
    return {
        "92": {
            "inputs": {"filename_prefix": "video/MiniMax_H3", "video": ["130", 0]},
            "class_type": "SaveVideo",
        },
        "115": {
            "inputs": {"aspect_ratio": "16:9 (Widescreen)", "megapixels": 0.2, "multiple": 32},
            "class_type": "ResolutionSelector",
        },
        "119": {
            "inputs": {"vae_name": r"minimax\minimax_h3_video_vae_fp16.safetensors"},
            "class_type": "VAELoader",
        },
        "120": {
            "inputs": {"vae_name": r"minimax\minimax_h3_audio_vae_fp32.safetensors"},
            "class_type": "VAELoader",
        },
        "121": {
            "inputs": {"samples": ["125", 0], "vae": ["120", 0]},
            "class_type": "VAEDecodeAudio",
        },
        "122": {"inputs": {"samples": ["125", 0], "vae": ["119", 0]}, "class_type": "VAEDecode"},
        "123": {"inputs": {"sampler_name": "res_multistep"}, "class_type": "KSamplerSelect"},
        "124": {
            "inputs": {"scheduler": "simple", "steps": 20, "denoise": 1, "model": ["127", 0]},
            "class_type": "BasicScheduler",
        },
        "125": {
            "inputs": {
                "noise": ["129", 0],
                "guider": ["126", 0],
                "sampler": ["123", 0],
                "sigmas": ["124", 0],
                "latent_image": ["136", 1],
            },
            "class_type": "SamplerCustomAdvanced",
        },
        "126": {
            "inputs": {"model": ["127", 0], "conditioning": ["147", 0]},
            "class_type": "BasicGuider",
        },
        "127": {
            "inputs": {
                "unet_name": r"minimax\minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
            "class_type": "UNETLoader",
        },
        "128": {
            "inputs": {
                "clip_name": r"minimax\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "type": "minimax",
                "device": "default",
            },
            "class_type": "CLIPLoader",
        },
        "129": {"inputs": {"noise_seed": 123456}, "class_type": "RandomNoise"},
        "130": {
            "inputs": {
                "fps": 24,
                "bit_depth": 8,
                "color_space": "sRGB",
                "codec": "none",
                "images": ["122", 0],
                "audio": ["121", 0],
            },
            "class_type": "CreateVideo",
        },
        "131": {
            "inputs": {"expression": "old", "values.a": ["132", 0]},
            "class_type": "ComfyMathExpression",
        },
        "132": {"inputs": {"value": 7}, "class_type": "PrimitiveFloat"},
        "136": {
            "inputs": {
                "prompt": ["138", 0],
                "width": ["115", 0],
                "height": ["115", 1],
                "length": ["131", 1],
                "ref_image_size": "match",
                "clip": ["128", 0],
                "vae": ["119", 0],
                "audio_vae": ["120", 0],
                "ref_images.ref_image_0": ["137", 0],
                "ref_images.ref_image_1": ["139", 0],
                "ref_images.ref_image_2": ["141", 0],
                "ref_images.ref_image_3": ["142", 0],
                "ref_images.ref_image_4": ["143", 0],
            },
            "class_type": "MiniMaxH3ReferenceToVideo",
        },
        "137": {"inputs": {"image": "james.png"}, "class_type": "LoadImage"},
        "138": {"inputs": {"value": "old prompt"}, "class_type": "PrimitiveStringMultiline"},
        "139": {"inputs": {"image": "sandra.png"}, "class_type": "LoadImage"},
        "141": {"inputs": {"image": "ros.png"}, "class_type": "LoadImage"},
        "142": {"inputs": {"image": "bridge.png"}, "class_type": "LoadImage"},
        "143": {"inputs": {"image": "xorix.png"}, "class_type": "LoadImage"},
        "144": {
            "inputs": {
                "frame_idx": 0,
                "positive": ["136", 0],
                "latent": ["136", 1],
                "vae": ["119", 0],
                "image": ["145", 0],
            },
            "class_type": "MiniMaxH3AddGuide",
        },
        "145": {"inputs": {"image": "opening.png"}, "class_type": "LoadImage"},
        "146": {"inputs": {"image": "rejected-frame96.png"}, "class_type": "LoadImage"},
        "147": {
            "inputs": {
                "frame_idx": 96,
                "positive": ["144", 0],
                "latent": ["136", 1],
                "vae": ["119", 0],
                "image": ["146", 0],
            },
            "class_type": "MiniMaxH3AddGuide",
        },
    }


def _write_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, Path]]:
    project = tmp_path / "project"
    input_root = tmp_path / "input"
    project.mkdir()
    input_root.mkdir()
    files = {}
    for name in ("james", "sandra", "bridge", "xorix", "ros", "opening", "intro"):
        path = project / f"{name}.png"
        path.write_bytes(name.encode())
        files[name] = path
    workflow = (
        project
        / "resources"
        / "workflows"
        / "manual"
        / "minimax_h3_ref2va_sht002_baseline_api.json"
    )
    workflow.parent.mkdir(parents=True)
    workflow.write_text(json.dumps(_workflow()), encoding="utf-8")
    return project, input_root, files


def _slot(index: int, name: str, asset_id: str, source: Path) -> SpanReferenceSlot:
    return SpanReferenceSlot(
        picture_index=index,
        picture_tag=f"<Picture {index}>",
        reference_id=f"REF-{name.upper()}",
        asset_id=asset_id,
        role="identity",
        source_path=str(source),
        semantic_label=name,
    )


def _execution(
    files: dict[str, Path],
    *,
    sequence: int,
) -> MiniMaxH3SpanExecution:
    if sequence == 1:
        refs = (
            _slot(1, "james", "CAP-CHR-001", files["james"]),
            _slot(2, "sandra", "CAP-CHR-003", files["sandra"]),
            _slot(3, "bridge", "CAP-LOC-021", files["bridge"]),
            _slot(4, "xorix", "CAP-PLN-002", files["xorix"]),
        )
        return MiniMaxH3SpanExecution(
            span_id="SPAN-001",
            sequence_number=1,
            global_start_frame=0,
            global_through_frame=95,
            governed_frame_count=96,
            provider_frame_count=107,
            reference_slots=refs,
            positive_prompt="James left. Sandra right. Bridge and Xorix stable.",
            negative_prompt="extra people; cuts",
            motion_prompt="Subtle stable bridge motion.",
            guide_source_kind="shot_opening_authority",
            guide_image_path=str(files["opening"]),
            guide_image_sha256=_sha(files["opening"]),
            guide_frame_idx=0,
            source_span_input_id="INPUT-1",
            source_span_input_plan_fingerprint="plan-fingerprint",
        )
    refs = (
        _slot(1, "james", "CAP-CHR-001", files["james"]),
        _slot(2, "sandra", "CAP-CHR-003", files["sandra"]),
        _slot(3, "bridge", "CAP-LOC-021", files["bridge"]),
        _slot(4, "xorix", "CAP-PLN-002", files["xorix"]),
        _slot(5, "ros", "CAP-CHR-005", files["ros"]),
    )
    return MiniMaxH3SpanExecution(
        span_id="SPAN-002",
        sequence_number=2,
        global_start_frame=96,
        global_through_frame=143,
        governed_frame_count=48,
        provider_frame_count=56,
        reference_slots=refs,
        positive_prompt="James left. Sandra right. Ros enters from far left.",
        negative_prompt="extra people; cuts",
        motion_prompt="Ros continues a natural entrance.",
        guide_source_kind="governed_introduction_keyframe",
        guide_image_path=str(files["intro"]),
        guide_image_sha256=_sha(files["intro"]),
        guide_frame_idx=0,
        source_span_input_id="INPUT-2",
        source_span_input_plan_fingerprint="plan-fingerprint",
    )


def _sha(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_h3_workflow_compiler_removes_future_ros_and_second_guide_from_span1(
    tmp_path: Path,
) -> None:
    project, input_root, files = _write_inputs(tmp_path)
    compiled = MiniMaxH3ComfyUIWorkflowCompiler(
        project,
        comfyui_input_directory=input_root,
    ).compile(_execution(files, sequence=1))

    serialized = json.dumps(compiled.workflow)
    assert "Ros" not in serialized
    assert "ros.png" not in serialized
    assert "rejected-frame96.png" not in serialized
    assert "146" not in compiled.workflow
    assert "147" not in compiled.workflow
    assert compiled.workflow["126"]["inputs"]["conditioning"] == ["144", 0]
    assert compiled.workflow["144"]["inputs"]["frame_idx"] == 0
    assert compiled.workflow["136"]["inputs"]["length"] == 107
    assert "131" not in compiled.workflow
    assert "132" not in compiled.workflow
    ref_keys = sorted(
        key for key in compiled.workflow["136"]["inputs"] if key.startswith("ref_images.ref_image_")
    )
    assert ref_keys == [
        "ref_images.ref_image_0",
        "ref_images.ref_image_1",
        "ref_images.ref_image_2",
        "ref_images.ref_image_3",
    ]


def test_h3_workflow_compiler_adds_ros_only_to_span2(tmp_path: Path) -> None:
    project, input_root, files = _write_inputs(tmp_path)
    compiled = MiniMaxH3ComfyUIWorkflowCompiler(
        project,
        comfyui_input_directory=input_root,
    ).compile(_execution(files, sequence=2))

    serialized = json.dumps(compiled.workflow)
    assert "Ros enters from far left" in serialized
    assert compiled.workflow["136"]["inputs"]["length"] == 56
    assert "ref_images.ref_image_4" in compiled.workflow["136"]["inputs"]
    assert "146" not in compiled.workflow
    assert "147" not in compiled.workflow


def test_h3_workflow_compiler_keeps_proven_models_sampler_and_seed(tmp_path: Path) -> None:
    project, input_root, files = _write_inputs(tmp_path)
    compiled = MiniMaxH3ComfyUIWorkflowCompiler(
        project,
        comfyui_input_directory=input_root,
    ).compile(_execution(files, sequence=1))

    assert compiled.workflow["127"]["inputs"]["unet_name"] == (
        r"minimax\minimax_h3_ref2va_pruned_int8_convrot.safetensors"
    )
    assert compiled.workflow["128"]["inputs"]["clip_name"] == (
        r"minimax\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
    )
    assert compiled.workflow["123"]["inputs"]["sampler_name"] == "res_multistep"
    assert compiled.workflow["124"]["inputs"]["steps"] == 20
    assert compiled.workflow["129"]["inputs"]["noise_seed"] == 123456
    assert compiled.workflow["130"]["inputs"]["fps"] == 24
    assert len(compiled.workflow_fingerprint) == 64
    assert len(compiled.model_config_fingerprint) == 64


class _Transport:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.prompt_id = "PROMPT-H3-001"

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> object:
        self.calls.append((method, path, payload))
        if method == "POST" and path == "/prompt":
            video = self.output_root / "video" / "VSCS_H3" / "test.mp4"
            video.parent.mkdir(parents=True, exist_ok=True)
            video.write_bytes(b"mp4")
            return {"prompt_id": self.prompt_id}
        if method == "GET" and path == f"/history/{self.prompt_id}":
            return {
                self.prompt_id: {
                    "status": {"status_str": "success", "completed": True},
                    "outputs": {
                        "92": {
                            "gifs": [
                                {
                                    "filename": "test.mp4",
                                    "subfolder": "video/VSCS_H3",
                                    "type": "output",
                                }
                            ]
                        }
                    },
                }
            }
        if method == "POST" and path == "/free":
            return {}
        raise AssertionError(f"Unexpected request: {method} {path}")


def test_live_h3_provider_submits_exact_isolated_workflow_and_persists_evidence(
    tmp_path: Path,
) -> None:
    project, input_root, files = _write_inputs(tmp_path)
    output_root = tmp_path / "output"
    output_root.mkdir()
    transport = _Transport(output_root)
    execution = _execution(files, sequence=1)
    provider = LiveMiniMaxH3ComfyUISpanProvider(
        project,
        endpoint="http://127.0.0.1:8188",
        comfyui_input_directory=input_root,
        comfyui_output_directory=output_root,
        poll_interval_seconds=0,
        transport=transport,
    )

    output = provider.render(execution)
    evidence = provider.execution_evidence(execution)
    provider.free_models_and_memory()

    assert output.is_file()
    assert evidence["job_id"] == execution.job_id
    assert evidence["provider_frame_count"] == 107
    assert evidence["governed_frame_count"] == 96
    assert len(str(evidence["workflow_fingerprint"])) == 64
    assert len(str(evidence["model_config_fingerprint"])) == 64
    prompt_calls = [
        payload
        for method, path, payload in transport.calls
        if method == "POST" and path == "/prompt"
    ]
    assert len(prompt_calls) == 1
    serialized = json.dumps(prompt_calls[0])
    assert "Ros" not in serialized
    assert "frame_idx" in serialized
    assert ("POST", "/free", {"unload_models": True, "free_memory": True}) in transport.calls
