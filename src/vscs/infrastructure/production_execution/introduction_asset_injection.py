"""ComfyUI provider for Phase 20.18.2.3.6.2 identity-locked asset injection."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from PIL import Image

from vscs.application.production_execution import (
    IntroductionInjectionRequest,
    IntroductionInjectionResult,
)
from vscs.application.production_execution.automated_introduction_boundary import (
    file_sha256,
    now_iso,
)
from vscs.application.production_execution.introduction_asset_injection_authority import (
    IntroductionInjectionRegionCompiler,
)
from vscs.infrastructure.xcic_core import XCICCoreClient, XCICCoreClientError


class ComfyUIIntroductionInjectionSynthesisError(RuntimeError):
    """Raised when governed identity-locked image injection cannot complete."""


class ComfyUIIntroductionInjectionSynthesizer:
    """Edit only the governed edge region, then composite it onto the exact source plate."""

    WORKFLOW_FILE = (
        Path("src")
        / "vscs"
        / "workflows"
        / "image"
        / "VSCS_Qwen_Identity_Locked_Injection_Workflow_API_v1.json"
    )
    LOADER_NODE = "1"
    LOADER_CLASS = "VSCSIntroductionBoundaryPackageLoaderV1"
    PROVIDER_NAME = "ComfyUI — Qwen Identity-Locked Injection v1"
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

    def preflight(self) -> None:
        workflow = self._workflow()
        try:
            self.client.healthcheck()
            self.client.validate_nodes(workflow)
        except XCICCoreClientError as exc:
            raise ComfyUIIntroductionInjectionSynthesisError(
                f"Identity-locked injection provider preflight failed: {exc}"
            ) from exc

    def synthesize(
        self,
        request: IntroductionInjectionRequest,
        *,
        attempt_number: int,
    ) -> IntroductionInjectionResult:
        if request.injection_version != "3.6.2":
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Identity-locked injection requires Phase 3.6.2 request authority"
            )
        if attempt_number <= 0:
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Identity-locked injection attempt_number must be positive"
            )

        source = self._project_file(request.source_boundary_image_path, "source boundary")
        if file_sha256(source) != request.source_boundary_image_sha256:
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Source boundary checksum changed before identity-locked injection"
            )
        self._validate_geometry(source, request.width, request.height, "source boundary")

        reference_paths = tuple(
            self._project_file(path, f"canonical reference {reference_id}")
            for reference_id, path in zip(
                request.canonical_asset.reference_ids,
                request.canonical_asset.reference_paths,
                strict=True,
            )
        )
        for reference_id, reference_path, expected_sha in zip(
            request.canonical_asset.reference_ids,
            reference_paths,
            request.canonical_asset.reference_sha256,
            strict=True,
        ):
            if file_sha256(reference_path) != expected_sha:
                raise ComfyUIIntroductionInjectionSynthesisError(
                    f"Canonical injection reference checksum changed: {reference_id}"
                )

        root = (
            self.project_directory
            / ".vscs"
            / "introduction_injection"
            / request.shot_id
            / request.requirement_id
            / request.request_id
        )
        root.mkdir(parents=True, exist_ok=True)
        final_path = root / f"frame-{request.target_global_frame_index:06d}.png"
        if final_path.exists():
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Immutable injection attempt already contains a final candidate"
            )

        pixel_box = IntroductionInjectionRegionCompiler.pixel_box(
            request.injection_region,
            width=request.width,
            height=request.height,
        )
        crop_path = root / "source-region.png"
        self._write_source_crop(source, crop_path, pixel_box)
        crop_width = pixel_box[2] - pixel_box[0]
        crop_height = pixel_box[3] - pixel_box[1]

        current_source = crop_path
        workflow = self._workflow()
        try:
            self.preflight()
            for index, (reference_id, reference_path, reference_sha) in enumerate(
                zip(
                    request.canonical_asset.reference_ids,
                    reference_paths,
                    request.canonical_asset.reference_sha256,
                    strict=True,
                ),
                start=1,
            ):
                output_name = f"pass-{index:03d}.png"
                output_path = root / output_name
                if output_path.exists():
                    raise ComfyUIIntroductionInjectionSynthesisError(
                        f"Immutable injection pass already exists: {output_path.name}"
                    )
                request_path = root / f"pass-{index:03d}-request.json"
                if request_path.exists():
                    raise ComfyUIIntroductionInjectionSynthesisError(
                        f"Immutable injection request already exists: {request_path.name}"
                    )
                payload = self._runtime_payload(
                    request,
                    source_path=current_source,
                    reference_id=reference_id,
                    reference_path=reference_path,
                    reference_sha=reference_sha,
                    output_directory=root,
                    output_filename=output_name,
                    width=crop_width,
                    height=crop_height,
                    pixel_box=pixel_box,
                    pass_index=index,
                )
                request_path.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                prompt = json.loads(json.dumps(workflow))
                prompt[self.LOADER_NODE]["inputs"]["request_file"] = str(request_path)
                prompt_id = self.client.submit(prompt)
                self.client.wait(prompt_id, timeout_seconds=self.timeout_seconds)
                generated = self._wait_for_output(output_path)
                self._validate_geometry(
                    generated,
                    crop_width,
                    crop_height,
                    f"injection pass {index}",
                )
                current_source = generated
        except (XCICCoreClientError, OSError, ValueError) as exc:
            raise ComfyUIIntroductionInjectionSynthesisError(str(exc)) from exc

        self._composite_region(
            source=source,
            injected_region=current_source,
            destination=final_path,
            pixel_box=pixel_box,
        )
        self._validate_geometry(final_path, request.width, request.height, "injected boundary")
        return IntroductionInjectionResult(
            request_id=request.request_id,
            requirement_id=request.requirement_id,
            image_path=str(final_path),
            image_sha256=file_sha256(final_path),
            canonical_asset_id=request.canonical_asset.authority_id,
            injection_region_id=request.injection_region.region_id,
            provider_name=self.PROVIDER_NAME,
            model=self.MODEL_NAME,
            generated_at=now_iso(),
            attempt_number=attempt_number,
        )

    def _runtime_payload(
        self,
        request: IntroductionInjectionRequest,
        *,
        source_path: Path,
        reference_id: str,
        reference_path: Path,
        reference_sha: str,
        output_directory: Path,
        output_filename: str,
        width: int,
        height: int,
        pixel_box: tuple[int, int, int, int],
        pass_index: int,
    ) -> dict[str, object]:
        side = request.injection_region.side.value.upper()
        positive_prompt = (
            "IDENTITY-LOCKED ASSET INJECTION. Edit only the supplied source-region image. "
            f"Inject exactly one canonical {request.canonical_asset.asset_kind}: "
            f"{request.canonical_asset.asset_id}. The canonical reference {reference_id} is "
            "immutable identity authority: preserve face, age, ethnicity, hairstyle, body "
            "proportions, clothing/uniform identity, insignia, and defining appearance. "
            f"This is the first visible phase of an ENTER transition from the {side} edge. "
            "Only a partial body may be visible; the subject must not appear fully arrived, "
            "settled, centered, oversized, or teleport into a complete standing pose. "
            "Preserve every pre-existing pixel relationship, person, object, lighting cue, "
            "camera perspective, and scene structure inside the supplied region except where "
            "strictly required to reveal this one entrant. Add no other person or asset. "
            f"Governed full-frame injection pixel box is {pixel_box}. "
            f"Maximum subject scale ratio is {request.injection_region.max_subject_scale_ratio:.4f}. "
            f"Injection pass {pass_index} must preserve the same single entrant."
        )
        negative_prompt = (
            "second entrant, duplicate person, extra background crew, central entrant, "
            "oversized entrant, dominant foreground person, fully arrived entrant, full settled "
            "standing pose, both feet fully established, teleportation, wrong face, identity "
            "drift, altered existing people, moved existing people, scene redesign, camera change, "
            "lighting change, architecture change, added prop, added object"
        )
        return {
            "schema_version": "1.0",
            "injection_version": request.injection_version,
            "request_id": request.request_id,
            "shot_id": request.shot_id,
            "requirement_id": request.requirement_id,
            "source_boundary_image_path": str(source_path),
            "source_boundary_image_sha256": file_sha256(source_path),
            "introduced_reference_ids": [reference_id],
            "introduced_reference_paths": [str(reference_path)],
            "introduced_reference_sha256": [reference_sha],
            "canonical_asset_id": request.canonical_asset.asset_id,
            "canonical_asset_authority_id": request.canonical_asset.authority_id,
            "injection_region": request.injection_region.to_dict(),
            "injection_pixel_box": list(pixel_box),
            "positive_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "seed": request.seed + pass_index - 1,
            "source_package_fingerprint": request.source_package_fingerprint,
            "timed_asset_presence_fingerprint": request.timed_asset_presence_fingerprint,
            "output_directory": str(output_directory),
            "output_filename": output_filename,
            "enable_lightning_lora": True,
        }

    def _workflow(self) -> dict[str, Any]:
        repository_root = Path(__file__).resolve().parents[4]
        path = repository_root / self.WORKFLOW_FILE
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ComfyUIIntroductionInjectionSynthesisError(
                f"Cannot load identity-locked injection workflow: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Identity-locked injection workflow root must be an object"
            )
        loader = raw.get(self.LOADER_NODE)
        if not isinstance(loader, dict) or not isinstance(loader.get("inputs"), dict):
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Identity-locked injection workflow loader is missing"
            )
        if loader.get("class_type") != self.LOADER_CLASS:
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Identity-locked injection workflow has the wrong loader"
            )
        if (
            loader["inputs"].get("request_file")
            != "__VSCS_INTRODUCTION_INJECTION_REQUEST__"
        ):
            raise ComfyUIIntroductionInjectionSynthesisError(
                "Identity-locked injection workflow template marker changed"
            )
        return raw

    def _project_file(self, value: str, label: str) -> Path:
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.project_directory / path
        resolved = path.resolve(strict=False)
        if not resolved.is_relative_to(self.project_directory):
            raise ComfyUIIntroductionInjectionSynthesisError(
                f"{label} must remain inside the VSCS project"
            )
        if not resolved.is_file():
            raise ComfyUIIntroductionInjectionSynthesisError(
                f"{label} does not exist: {resolved}"
            )
        return resolved

    @staticmethod
    def _write_source_crop(
        source: Path,
        destination: Path,
        pixel_box: tuple[int, int, int, int],
    ) -> None:
        with Image.open(source) as image:
            image.convert("RGB").crop(pixel_box).save(destination)

    @staticmethod
    def _composite_region(
        *,
        source: Path,
        injected_region: Path,
        destination: Path,
        pixel_box: tuple[int, int, int, int],
    ) -> None:
        with Image.open(source) as source_image, Image.open(injected_region) as region_image:
            composed = source_image.convert("RGB").copy()
            composed.paste(region_image.convert("RGB"), (pixel_box[0], pixel_box[1]))
            composed.save(destination)

    @staticmethod
    def _validate_geometry(path: Path, width: int, height: int, label: str) -> None:
        try:
            with Image.open(path) as image:
                actual = image.size
        except (OSError, ValueError) as exc:
            raise ComfyUIIntroductionInjectionSynthesisError(
                f"{label} is not a readable image: {exc}"
            ) from exc
        if actual != (width, height):
            raise ComfyUIIntroductionInjectionSynthesisError(
                f"{label} geometry changed: {actual} != {(width, height)}"
            )

    @staticmethod
    def _wait_for_output(expected: Path) -> Path:
        deadline = time.monotonic() + 10.0
        while time.monotonic() <= deadline:
            if expected.is_file():
                return expected
            time.sleep(0.25)
        raise ComfyUIIntroductionInjectionSynthesisError(
            "ComfyUI completed without writing the expected injected-region image "
            f"in {expected.parent}"
        )
