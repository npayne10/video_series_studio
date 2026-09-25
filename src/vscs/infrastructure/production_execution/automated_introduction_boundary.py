"""Qwen Image Edit provider for automated introduction-boundary synthesis."""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from PIL import Image

from vscs.application.production_execution.automated_introduction_boundary import (
    AutomatedBoundaryValidationState,
    AutomatedIntroductionBoundaryError,
    AutomatedIntroductionBoundaryRequest,
    AutomatedIntroductionBoundaryResult,
    file_sha256,
    now_iso,
)
from vscs.infrastructure.xcic_core import XCICCoreClient, XCICCoreClientError


class ComfyUIIntroductionBoundarySynthesisError(RuntimeError):
    """Raised when the governed Qwen introduction-boundary workflow cannot complete."""


class ComfyUIIntroductionBoundarySynthesizer:
    """Use source frame + canonical introduced reference to synthesize the next exact frame."""

    WORKFLOW_FILE = (
        Path("src")
        / "vscs"
        / "workflows"
        / "image"
        / "VSCS_Qwen_Introduction_Boundary_Workflow_API_v1.json"
    )
    LOADER_NODE = "1"
    PROVIDER_NAME = "ComfyUI — Qwen Introduction Boundary v1"
    MODEL_NAME = "Qwen Image Edit 2511 + Lightning 4-step"

    def __init__(
        self,
        project_directory: Path,
        *,
        base_url: str = "http://127.0.0.1:8188",
        timeout_seconds: float = 3600.0,
        client: XCICCoreClient | None = None,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = client or XCICCoreClient(self.base_url)

    def synthesize(
        self,
        request: AutomatedIntroductionBoundaryRequest,
    ) -> AutomatedIntroductionBoundaryResult:
        if request.strategy.value != "synthesized_keyframe":
            raise ComfyUIIntroductionBoundarySynthesisError(
                f"Qwen synthesis cannot execute strategy {request.strategy.value}"
            )
        source = self._project_file(request.source_boundary_image_path, "source boundary")
        if file_sha256(source) != request.source_boundary_image_sha256:
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Source boundary checksum changed before automated synthesis"
            )
        if not request.introduced_reference_paths:
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Automated synthesis requires at least one canonical introduced reference"
            )

        workflow = self._workflow()
        root = (
            self.project_directory
            / ".vscs"
            / "automated_introduction_boundaries"
            / request.shot_id
            / request.requirement_id
        )
        root.mkdir(parents=True, exist_ok=True)

        current_source = source
        current_source_sha = request.source_boundary_image_sha256
        try:
            self.client.healthcheck()
            self.client.validate_nodes(workflow)
            for index, (reference_id, reference_path_raw, reference_sha) in enumerate(
                zip(
                    request.introduced_reference_ids,
                    request.introduced_reference_paths,
                    request.introduced_reference_sha256,
                    strict=True,
                ),
                start=1,
            ):
                reference_path = self._project_file(
                    reference_path_raw,
                    f"introduced reference {reference_id}",
                )
                if file_sha256(reference_path) != reference_sha:
                    raise ComfyUIIntroductionBoundarySynthesisError(
                        f"Introduced canonical reference checksum changed: {reference_id}"
                    )

                output_name = f"pass-{index:03d}.png"
                output_path = root / output_name
                pass_request = replace(
                    request,
                    source_boundary_image_path=str(current_source),
                    source_boundary_image_sha256=current_source_sha,
                    introduced_reference_ids=(reference_id,),
                    introduced_reference_paths=(str(reference_path),),
                    introduced_reference_sha256=(reference_sha,),
                    positive_prompt=(
                        request.positive_prompt
                        + " In this synthesis pass introduce only the exact canonical asset "
                        f"represented by {reference_id}; preserve every other visible element."
                    ),
                    seed=request.seed + index - 1,
                )
                request_path = root / f"pass-{index:03d}-request.json"
                payload = pass_request.to_dict()
                payload["output_directory"] = str(root)
                payload["output_filename"] = output_name
                payload["enable_lightning_lora"] = True
                request_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                prompt = json.loads(json.dumps(workflow))
                prompt[self.LOADER_NODE]["inputs"]["request_file"] = str(request_path)
                prompt_id = self.client.submit(prompt)
                self.client.wait(prompt_id, timeout_seconds=self.timeout_seconds)
                generated = self._wait_for_output(output_path, root)
                self._validate_geometry(generated, request.width, request.height)
                current_source = generated
                current_source_sha = file_sha256(generated)
        except (XCICCoreClientError, OSError, ValueError, AutomatedIntroductionBoundaryError) as exc:
            raise ComfyUIIntroductionBoundarySynthesisError(str(exc)) from exc

        final_path = root / f"frame-{request.target_global_frame_index:06d}.png"
        if current_source != final_path:
            final_path.write_bytes(current_source.read_bytes())
        final_sha = file_sha256(final_path)
        self._validate_geometry(final_path, request.width, request.height)
        return AutomatedIntroductionBoundaryResult(
            request_id=request.request_id,
            requirement_id=request.requirement_id,
            image_path=str(final_path),
            image_sha256=final_sha,
            provider_name=self.PROVIDER_NAME,
            model=self.MODEL_NAME,
            source_boundary_image_path=str(source),
            source_boundary_image_sha256=request.source_boundary_image_sha256,
            introduced_reference_ids=request.introduced_reference_ids,
            width=request.width,
            height=request.height,
            generated_at=now_iso(),
            validation_state=AutomatedBoundaryValidationState.PASSED,
            validation_findings=(
                "source_boundary_checksum_verified",
                "introduced_reference_checksums_verified",
                "output_geometry_verified",
                "final_visual_qc_deferred_to_assembled_shot",
            ),
        )

    def _workflow(self) -> dict[str, Any]:
        repository_root = Path(__file__).resolve().parents[4]
        path = repository_root / self.WORKFLOW_FILE
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ComfyUIIntroductionBoundarySynthesisError(
                f"Cannot load automated introduction-boundary workflow: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Automated introduction-boundary workflow root must be an object"
            )
        loader = raw.get(self.LOADER_NODE)
        if not isinstance(loader, dict) or not isinstance(loader.get("inputs"), dict):
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Automated introduction-boundary workflow loader is missing"
            )
        if loader.get("class_type") != "VSCSIntroductionBoundaryPackageLoaderV1":
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Automated introduction-boundary workflow has the wrong loader"
            )
        if loader["inputs"].get("request_file") != "__VSCS_INTRODUCTION_BOUNDARY_REQUEST__":
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Automated introduction-boundary workflow template marker changed"
            )
        return raw

    def _project_file(self, value: str, label: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.project_directory):
            raise ComfyUIIntroductionBoundarySynthesisError(
                f"{label} must remain inside the VSCS project"
            )
        if not resolved.is_file():
            raise ComfyUIIntroductionBoundarySynthesisError(
                f"{label} does not exist: {resolved}"
            )
        return resolved

    @staticmethod
    def _validate_geometry(path: Path, width: int, height: int) -> None:
        try:
            with Image.open(path) as image:
                actual = image.size
        except (OSError, ValueError) as exc:
            raise ComfyUIIntroductionBoundarySynthesisError(
                f"Generated introduction boundary is not a readable image: {exc}"
            ) from exc
        if actual != (width, height):
            raise ComfyUIIntroductionBoundarySynthesisError(
                "Generated introduction boundary geometry changed: "
                f"{actual} != {(width, height)}"
            )

    @staticmethod
    def _wait_for_output(expected: Path, output_root: Path) -> Path:
        deadline = time.monotonic() + 10.0
        while time.monotonic() <= deadline:
            if expected.is_file():
                return expected
            candidates = tuple(output_root.glob("pass-*.png"))
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime_ns)
            time.sleep(0.25)
        raise ComfyUIIntroductionBoundarySynthesisError(
            f"ComfyUI completed without writing the expected introduction frame in {output_root}"
        )
