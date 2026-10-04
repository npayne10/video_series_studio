"""Live ComfyUI binding for governed MiniMax H3 isolated spans."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar

from vscs.infrastructure.rendering import (
    ComfyUIClient,
    ComfyUITransport,
    UrllibComfyUITransport,
)

from .minimax_h3_span_adapter import MiniMaxH3SpanExecution


class MiniMaxH3ComfyUIProviderError(RuntimeError):
    """Raised when a governed H3 span cannot be compiled or executed safely."""


@dataclass(frozen=True, slots=True)
class MiniMaxH3ComfyUICompiledJob:
    """Exact provider payload and fingerprints for one isolated H3 span."""

    job_id: str
    workflow: dict[str, object]
    workflow_fingerprint: str
    model_config_fingerprint: str
    staged_input_names: tuple[str, ...]
    filename_prefix: str


class MiniMaxH3ComfyUIWorkflowCompiler:
    """Bind one governed H3 span to the proven Ref2VA API workflow."""

    REFERENCE_LOADER_IDS = ("137", "139", "141", "142", "143")
    REQUIRED_NODE_TYPES: ClassVar[dict[str, str]] = {
        "92": "SaveVideo",
        "115": "ResolutionSelector",
        "119": "VAELoader",
        "120": "VAELoader",
        "123": "KSamplerSelect",
        "124": "BasicScheduler",
        "125": "SamplerCustomAdvanced",
        "126": "BasicGuider",
        "127": "UNETLoader",
        "128": "CLIPLoader",
        "129": "RandomNoise",
        "130": "CreateVideo",
        "136": "MiniMaxH3ReferenceToVideo",
        "138": "PrimitiveStringMultiline",
        "144": "MiniMaxH3AddGuide",
        "145": "LoadImage",
    }

    def __init__(
        self,
        project_directory: Path,
        *,
        comfyui_input_directory: Path,
        workflow_path: Path | None = None,
        seed: int = 123456,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.comfyui_input_directory = (
            Path(comfyui_input_directory).expanduser().resolve(strict=False)
        )
        self.workflow_path = (
            Path(workflow_path).expanduser().resolve(strict=False)
            if workflow_path is not None
            else (
                self.project_directory
                / "resources"
                / "workflows"
                / "manual"
                / "minimax_h3_ref2va_sht002_baseline_api.json"
            ).resolve(strict=False)
        )
        self.seed = seed

    def compile(self, execution: MiniMaxH3SpanExecution) -> MiniMaxH3ComfyUICompiledJob:
        workflow = self._load()
        self._require_baseline(workflow)
        if len(execution.reference_slots) > len(self.REFERENCE_LOADER_IDS):
            raise MiniMaxH3ComfyUIProviderError(
                "H3 baseline supports at most five active canonical references"
            )

        staged_names: list[str] = []
        active_loader_ids: list[str] = []
        for slot, loader_id in zip(
            execution.reference_slots,
            self.REFERENCE_LOADER_IDS,
            strict=False,
        ):
            source = self._resolve_source(slot.source_path)
            staged = self._stage(
                source,
                execution.job_id,
                f"ref-{slot.picture_index:02d}-{source.name}",
            )
            staged_names.append(staged)
            active_loader_ids.append(loader_id)
            self._node_inputs(workflow, loader_id)["image"] = staged

        reference_inputs = self._node_inputs(workflow, "136")
        for key in tuple(reference_inputs):
            if key.startswith("ref_images.ref_image_"):
                reference_inputs.pop(key)
        for index, loader_id in enumerate(active_loader_ids):
            reference_inputs[f"ref_images.ref_image_{index}"] = [loader_id, 0]

        for loader_id in self.REFERENCE_LOADER_IDS[len(active_loader_ids) :]:
            workflow.pop(loader_id, None)

        guide_source = self._resolve_source(execution.guide_image_path)
        if _sha256(guide_source) != execution.guide_image_sha256:
            raise MiniMaxH3ComfyUIProviderError(
                "H3 guide image checksum does not match governed execution authority"
            )
        guide_name = self._stage(
            guide_source,
            execution.job_id,
            f"guide-{execution.guide_image_sha256[:12]}-{guide_source.name}",
        )
        staged_names.append(guide_name)
        self._node_inputs(workflow, "145")["image"] = guide_name

        # d.2 proved that the historical second in-job guide is not an asset gate.
        workflow.pop("146", None)
        workflow.pop("147", None)
        self._node_inputs(workflow, "126")["conditioning"] = ["144", 0]
        self._node_inputs(workflow, "144")["frame_idx"] = 0

        prompt = self._provider_prompt(execution)
        self._node_inputs(workflow, "138")["value"] = prompt

        # Use the exact native frame count compiled by 6.4c rather than the old
        # duration-expression helper that produced the 175-frame monolithic tests.
        reference_inputs["length"] = execution.provider_frame_count
        workflow.pop("131", None)
        workflow.pop("132", None)

        self._node_inputs(workflow, "129")["noise_seed"] = self.seed
        self._node_inputs(workflow, "130")["fps"] = 24
        filename_prefix = f"video/VSCS_H3/{execution.job_id}"
        self._node_inputs(workflow, "92")["filename_prefix"] = filename_prefix

        self._require_isolated_payload(workflow, execution, tuple(staged_names))
        return MiniMaxH3ComfyUICompiledJob(
            job_id=execution.job_id,
            workflow=workflow,
            workflow_fingerprint=_fingerprint(workflow),
            model_config_fingerprint=self._model_config_fingerprint(workflow),
            staged_input_names=tuple(staged_names),
            filename_prefix=filename_prefix,
        )

    def _load(self) -> dict[str, object]:
        try:
            raw = json.loads(self.workflow_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MiniMaxH3ComfyUIProviderError(f"Cannot load H3 API workflow: {exc}") from exc
        if not isinstance(raw, dict):
            raise MiniMaxH3ComfyUIProviderError("H3 API workflow root must be an object")
        return copy.deepcopy({str(key): value for key, value in raw.items()})

    def _require_baseline(self, workflow: dict[str, object]) -> None:
        for node_id, class_type in self.REQUIRED_NODE_TYPES.items():
            raw = workflow.get(node_id)
            if not isinstance(raw, dict) or raw.get("class_type") != class_type:
                raise MiniMaxH3ComfyUIProviderError(
                    f"H3 baseline node {node_id} must be {class_type}"
                )
        if self._node_inputs(workflow, "127").get("unet_name") != (
            r"minimax\minimax_h3_ref2va_pruned_int8_convrot.safetensors"
        ):
            raise MiniMaxH3ComfyUIProviderError("Unexpected H3 diffusion model")
        if self._node_inputs(workflow, "128").get("clip_name") != (
            r"minimax\qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
        ):
            raise MiniMaxH3ComfyUIProviderError("Unexpected H3 text encoder")
        if self._node_inputs(workflow, "119").get("vae_name") != (
            r"minimax\minimax_h3_video_vae_fp16.safetensors"
        ):
            raise MiniMaxH3ComfyUIProviderError("Unexpected H3 video VAE")
        if self._node_inputs(workflow, "120").get("vae_name") != (
            r"minimax\minimax_h3_audio_vae_fp32.safetensors"
        ):
            raise MiniMaxH3ComfyUIProviderError("Unexpected H3 audio VAE")
        if self._node_inputs(workflow, "123").get("sampler_name") != "res_multistep":
            raise MiniMaxH3ComfyUIProviderError("Unexpected H3 sampler")
        scheduler = self._node_inputs(workflow, "124")
        if (
            scheduler.get("scheduler") != "simple"
            or scheduler.get("steps") != 20
            or scheduler.get("denoise") != 1
        ):
            raise MiniMaxH3ComfyUIProviderError("Unexpected H3 scheduler configuration")
        if self._node_inputs(workflow, "136").get("ref_image_size") != "match":
            raise MiniMaxH3ComfyUIProviderError("H3 ref_image_size must remain match")

    def _resolve_source(self, raw_path: str) -> Path:
        candidate = Path(raw_path).expanduser()
        possibilities = [candidate]
        if not candidate.is_absolute():
            possibilities.extend(
                (
                    self.project_directory / candidate,
                    self.comfyui_input_directory / candidate,
                    self.comfyui_input_directory / candidate.name,
                )
            )
        for possibility in possibilities:
            resolved = possibility.resolve(strict=False)
            if resolved.is_file():
                return resolved
        raise MiniMaxH3ComfyUIProviderError(f"H3 governed input image does not exist: {raw_path}")

    def _stage(self, source: Path, job_id: str, filename: str) -> str:
        destination_directory = self.comfyui_input_directory / "vscs_h3" / job_id
        destination_directory.mkdir(parents=True, exist_ok=True)
        destination = destination_directory / _safe_filename(filename)
        if destination.resolve(strict=False) != source.resolve(strict=False):
            shutil.copy2(source, destination)
        if _sha256(destination) != _sha256(source):
            raise MiniMaxH3ComfyUIProviderError(f"H3 staged input checksum changed: {destination}")
        return (PurePosixPath("vscs_h3") / job_id / destination.name).as_posix()

    @staticmethod
    def _provider_prompt(execution: MiniMaxH3SpanExecution) -> str:
        return (
            f"{execution.positive_prompt.strip()}\n\n"
            f"Motion:\n{execution.motion_prompt.strip()}\n\n"
            f"Negative constraints:\n{execution.negative_prompt.strip()}"
        )

    def _require_isolated_payload(
        self,
        workflow: dict[str, object],
        execution: MiniMaxH3SpanExecution,
        staged_names: tuple[str, ...],
    ) -> None:
        if "146" in workflow or "147" in workflow:
            raise MiniMaxH3ComfyUIProviderError(
                "H3 isolated span payload retained the historical second guide"
            )
        inputs = self._node_inputs(workflow, "136")
        ref_keys = sorted(key for key in inputs if key.startswith("ref_images.ref_image_"))
        expected_keys = [
            f"ref_images.ref_image_{index}" for index in range(len(execution.reference_slots))
        ]
        if ref_keys != expected_keys:
            raise MiniMaxH3ComfyUIProviderError(
                "H3 provider reference inputs do not exactly match active span slots"
            )
        if inputs.get("length") != execution.provider_frame_count:
            raise MiniMaxH3ComfyUIProviderError(
                "H3 provider frame count differs from governed adapter authority"
            )
        if self._node_inputs(workflow, "144").get("frame_idx") != 0:
            raise MiniMaxH3ComfyUIProviderError(
                "H3 isolated span may use only a local frame-0 guide"
            )
        load_images = {
            str(raw.get("inputs", {}).get("image"))
            for raw in workflow.values()
            if isinstance(raw, dict)
            and raw.get("class_type") == "LoadImage"
            and isinstance(raw.get("inputs"), dict)
        }
        if load_images != set(staged_names):
            raise MiniMaxH3ComfyUIProviderError(
                "H3 payload contains an ungoverned or stale image input"
            )

    def _model_config_fingerprint(self, workflow: dict[str, object]) -> str:
        payload = {
            "unet": self._node_inputs(workflow, "127"),
            "clip": self._node_inputs(workflow, "128"),
            "video_vae": self._node_inputs(workflow, "119"),
            "audio_vae": self._node_inputs(workflow, "120"),
            "sampler": self._node_inputs(workflow, "123"),
            "scheduler": self._node_inputs(workflow, "124"),
            "resolution": self._node_inputs(workflow, "115"),
            "video": self._node_inputs(workflow, "130"),
            "seed": self.seed,
        }
        return _fingerprint(payload)

    @staticmethod
    def _node_inputs(workflow: dict[str, object], node_id: str) -> dict[str, Any]:
        node = workflow.get(node_id)
        if not isinstance(node, dict):
            raise MiniMaxH3ComfyUIProviderError(f"H3 workflow node is missing: {node_id}")
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise MiniMaxH3ComfyUIProviderError(f"H3 workflow node has no inputs: {node_id}")
        return inputs


class LiveMiniMaxH3ComfyUISpanProvider:
    """Execute isolated H3 jobs through the existing live ComfyUI HTTP contract."""

    def __init__(
        self,
        project_directory: Path,
        *,
        endpoint: str,
        comfyui_input_directory: Path,
        comfyui_output_directory: Path,
        workflow_path: Path | None = None,
        seed: int = 123456,
        poll_interval_seconds: float = 1.0,
        execution_timeout_seconds: float = 3600.0,
        transport: ComfyUITransport | None = None,
    ) -> None:
        if poll_interval_seconds < 0 or execution_timeout_seconds <= 0:
            raise ValueError("H3 polling and execution timeout values are invalid")
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.comfyui_output_directory = (
            Path(comfyui_output_directory).expanduser().resolve(strict=False)
        )
        self.poll_interval_seconds = poll_interval_seconds
        self.execution_timeout_seconds = execution_timeout_seconds
        normalized_endpoint = endpoint.strip().rstrip("/")
        if not normalized_endpoint:
            raise ValueError("H3 ComfyUI endpoint cannot be blank")
        resolved_transport = transport or UrllibComfyUITransport(
            normalized_endpoint,
            timeout_seconds=10.0,
        )
        self.client = ComfyUIClient(resolved_transport, normalized_endpoint)
        self.compiler = MiniMaxH3ComfyUIWorkflowCompiler(
            self.project_directory,
            comfyui_input_directory=comfyui_input_directory,
            workflow_path=workflow_path,
            seed=seed,
        )
        self.evidence_root = self.project_directory / ".vscs" / "h3_provider_jobs"

    def render(self, execution: MiniMaxH3SpanExecution) -> Path:
        compiled = self.compiler.compile(execution)
        payload: dict[str, object] = {
            "prompt": compiled.workflow,
            "client_id": execution.job_id,
            "extra_data": {
                "vscs_h3_job_id": execution.job_id,
                "span_id": execution.span_id,
                "workflow_fingerprint": compiled.workflow_fingerprint,
                "model_config_fingerprint": compiled.model_config_fingerprint,
            },
        }
        prompt_id = self.client.submit(payload)
        deadline = time.monotonic() + self.execution_timeout_seconds
        while time.monotonic() < deadline:
            history = self.client.history(prompt_id)
            if history is not None:
                status = history.get("status")
                if isinstance(status, dict) and bool(status.get("completed")):
                    status_str = str(status.get("status_str") or "").strip().lower()
                    if status_str not in {"success", "completed"}:
                        raise MiniMaxH3ComfyUIProviderError(
                            f"H3 provider execution failed: {status}"
                        )
                    output = self._output_path(history)
                    self._persist_evidence(
                        execution,
                        compiled,
                        prompt_id=prompt_id,
                        output_path=output,
                    )
                    return output
            if self.poll_interval_seconds:
                time.sleep(self.poll_interval_seconds)
        raise MiniMaxH3ComfyUIProviderError(f"H3 provider execution timed out: {execution.job_id}")

    def free_models_and_memory(self) -> None:
        self.client.free_models_and_memory()

    def execution_evidence(self, execution: MiniMaxH3SpanExecution) -> dict[str, object]:
        path = self.evidence_root / f"{execution.job_id}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise MiniMaxH3ComfyUIProviderError(
                f"Cannot read H3 provider execution evidence: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise MiniMaxH3ComfyUIProviderError("H3 provider execution evidence must be an object")
        return raw

    def _output_path(self, history: dict[str, object]) -> Path:
        outputs = history.get("outputs")
        if not isinstance(outputs, dict):
            raise MiniMaxH3ComfyUIProviderError("Completed H3 execution has no ComfyUI outputs")
        candidates: list[Path] = []
        for raw_node in outputs.values():
            if not isinstance(raw_node, dict):
                continue
            for key in ("videos", "gifs", "images"):
                rows = raw_node.get(key)
                if not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    filename = str(row.get("filename") or "").strip()
                    if not filename.lower().endswith(".mp4"):
                        continue
                    subfolder = str(row.get("subfolder") or "").strip()
                    candidate = (self.comfyui_output_directory / subfolder / filename).resolve(
                        strict=False
                    )
                    if candidate.is_file():
                        candidates.append(candidate)
        if len(candidates) != 1:
            raise MiniMaxH3ComfyUIProviderError(
                f"Expected one completed H3 MP4 output, found {len(candidates)}"
            )
        return candidates[0]

    def _persist_evidence(
        self,
        execution: MiniMaxH3SpanExecution,
        compiled: MiniMaxH3ComfyUICompiledJob,
        *,
        prompt_id: str,
        output_path: Path,
    ) -> None:
        self.evidence_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "provider_id": execution.provider_id,
            "job_id": execution.job_id,
            "span_id": execution.span_id,
            "sequence_number": execution.sequence_number,
            "prompt_id": prompt_id,
            "workflow_fingerprint": compiled.workflow_fingerprint,
            "model_config_fingerprint": compiled.model_config_fingerprint,
            "reference_slot_fingerprint": execution.reference_slot_fingerprint,
            "prompt_fingerprint": execution.prompt_fingerprint,
            "guide_image_sha256": execution.guide_image_sha256,
            "provider_frame_count": execution.provider_frame_count,
            "governed_frame_count": execution.governed_frame_count,
            "staged_input_names": list(compiled.staged_input_names),
            "filename_prefix": compiled.filename_prefix,
            "output_path": str(output_path),
            "output_sha256": _sha256(output_path),
        }
        (self.evidence_root / f"{execution.job_id}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def _safe_filename(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in {".", "-", "_"} else "_"
        for character in value
    )
    return cleaned or "input.png"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fingerprint(value: object) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()
