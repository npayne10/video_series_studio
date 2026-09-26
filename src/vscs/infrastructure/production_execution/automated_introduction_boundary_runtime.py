"""Automated introduction-boundary synthesis and validation runtime.

The runtime is provider-specific only at this infrastructure boundary. It consumes
provider-neutral Phase 20.18.2.3.6 synthesis requests and never mutates Shot/UPD authority.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import shutil
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from vscs.application.production_execution.automated_introduction_boundaries import (
    AutomatedIntroductionBoundaryError,
    IntroductionBoundarySynthesisRequest,
    IntroductionBoundarySynthesisResult,
    IntroductionBoundaryValidationResult,
)
from vscs.infrastructure.xcic_core import XCICCoreClient, XCICCoreClientError


class AutomatedIntroductionBoundaryRuntimeError(RuntimeError):
    """Raised when provider synthesis or automated validation cannot complete safely."""


@dataclass(frozen=True, slots=True)
class MappedComfyUIBoundarySynthesisConfiguration:
    """External API-format ComfyUI workflow used for boundary image editing."""

    workflow_path: Path
    mapping_path: Path
    output_directory: Path
    endpoint: str = "http://127.0.0.1:8188"

    @classmethod
    def from_environment(
        cls,
        *,
        output_directory: Path,
        endpoint: str,
    ) -> MappedComfyUIBoundarySynthesisConfiguration:
        workflow = os.environ.get("VSCS_INTRO_BOUNDARY_WORKFLOW", "").strip()
        mapping = os.environ.get("VSCS_INTRO_BOUNDARY_MAPPING", "").strip()
        if not workflow or not mapping:
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Automated Introduction Boundary synthesis is not configured. Set "
                "VSCS_INTRO_BOUNDARY_WORKFLOW and VSCS_INTRO_BOUNDARY_MAPPING to a validated "
                "API-format ComfyUI image-edit workflow and its semantic input mapping."
            )
        return cls(
            workflow_path=Path(workflow),
            mapping_path=Path(mapping),
            output_directory=Path(output_directory),
            endpoint=endpoint,
        )

    def validate(self) -> None:
        for path, label in (
            (self.workflow_path, "workflow"),
            (self.mapping_path, "mapping"),
        ):
            resolved = path.expanduser().resolve(strict=False)
            if not resolved.is_file():
                raise AutomatedIntroductionBoundaryRuntimeError(
                    f"Introduction Boundary {label} does not exist: {resolved}"
                )
        output = self.output_directory.expanduser().resolve(strict=False)
        if not output.is_dir():
            raise AutomatedIntroductionBoundaryRuntimeError(
                f"Configured ComfyUI output directory does not exist: {output}"
            )


class MappedComfyUIIntroductionBoundarySynthesizer:
    """Run a user-installed image-edit workflow without hard-coded ComfyUI node IDs."""

    provider_id = "comfyui.introduction-boundary-edit.v1"

    def __init__(
        self,
        project_directory: Path,
        configuration: MappedComfyUIBoundarySynthesisConfiguration,
    ) -> None:
        self.project_directory = Path(project_directory).expanduser().resolve(strict=False)
        self.configuration = configuration
        self.configuration.validate()
        self.client = XCICCoreClient(configuration.endpoint)

    def synthesize(
        self,
        request: IntroductionBoundarySynthesisRequest,
    ) -> IntroductionBoundarySynthesisResult:
        try:
            workflow = self._read_object(self.configuration.workflow_path, "workflow")
            mapping = self._read_object(self.configuration.mapping_path, "mapping")
            reference_paths = self._reference_paths(request)
            destination = (
                self.project_directory
                / ".vscs"
                / "automated_introduction_boundaries"
                / request.shot_id
                / request.requirement_id
            )
            destination.mkdir(parents=True, exist_ok=True)
            output_name = f"frame-{request.target_global_frame_index:06d}-{uuid4().hex[:8]}.png"
            values: dict[str, object] = {
                "source_image": str(request.source_boundary_image_path.resolve(strict=True)),
                "introduced_reference_images": [str(path.resolve(strict=True)) for path in reference_paths],
                "positive_prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "width": request.width,
                "height": request.height,
                "seed": self._seed(request),
                "output_directory": str(destination),
                "output_filename": output_name,
            }
            prompt = self._patch(workflow, mapping, values)
            self.client.healthcheck()
            self.client.validate_nodes(prompt)
            prompt_id = self.client.submit(prompt)
            history = self.client.wait(prompt_id)
            source_output = self._resolve_history_image(history)
            target = destination / output_name
            shutil.copy2(source_output, target)
        except (
            AutomatedIntroductionBoundaryRuntimeError,
            AutomatedIntroductionBoundaryError,
            XCICCoreClientError,
            OSError,
            ValueError,
        ) as exc:
            raise AutomatedIntroductionBoundaryRuntimeError(str(exc)) from exc

        digest = self._sha256(target)
        return IntroductionBoundarySynthesisResult(
            image_path=target,
            provider_id=self.provider_id,
            provider_job_id=prompt_id,
            request_fingerprint=request.fingerprint,
            output_sha256=digest,
        )

    def _reference_paths(
        self,
        request: IntroductionBoundarySynthesisRequest,
    ) -> tuple[Path, ...]:
        manifest = (
            self.project_directory
            / ".vscs"
            / "automated_introduction_boundaries"
            / request.shot_id
            / request.requirement_id
            / "reference_paths.json"
        )
        if not manifest.is_file():
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Automated boundary synthesis reference-path manifest is missing. "
                "The orchestration service must materialize governed introduced references first."
            )
        raw = self._read_object(manifest, "reference-path manifest")
        values = raw.get("introduced_reference_paths")
        if not isinstance(values, list):
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Boundary reference-path manifest introduced_reference_paths must be an array"
            )
        paths = tuple(Path(str(value)) for value in values)
        if len(paths) != len(request.introduced_reference_ids):
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Boundary reference-path manifest does not match governed introduced references"
            )
        if any(not path.is_file() for path in paths):
            raise AutomatedIntroductionBoundaryRuntimeError(
                "One or more governed introduced reference images are unavailable"
            )
        return paths

    def _resolve_history_image(self, history: dict[str, Any]) -> Path:
        outputs = history.get("outputs")
        if not isinstance(outputs, dict):
            raise AutomatedIntroductionBoundaryRuntimeError(
                "ComfyUI boundary synthesis returned no output collection"
            )
        candidates: list[Path] = []
        root = self.configuration.output_directory.expanduser().resolve(strict=False)
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            for collection in node_output.values():
                if not isinstance(collection, list):
                    continue
                for item in collection:
                    if not isinstance(item, dict):
                        continue
                    filename = str(item.get("filename") or "").strip()
                    if not filename:
                        continue
                    suffix = Path(filename).suffix.casefold()
                    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
                        continue
                    subfolder = str(item.get("subfolder") or "").strip()
                    candidate = (root / subfolder / filename).resolve(strict=False)
                    if candidate.is_relative_to(root) and candidate.is_file():
                        candidates.append(candidate)
        if not candidates:
            raise AutomatedIntroductionBoundaryRuntimeError(
                "ComfyUI boundary synthesis completed without a usable image output"
            )
        return candidates[-1]

    @staticmethod
    def _patch(
        workflow: dict[str, Any],
        mapping: dict[str, Any],
        values: dict[str, object],
    ) -> dict[str, Any]:
        import copy

        prompt = copy.deepcopy(workflow)
        for key, value in values.items():
            target = MappedComfyUIIntroductionBoundarySynthesizer._mapping_target(mapping, key)
            if target is None:
                if key in {"source_image", "introduced_reference_images", "positive_prompt", "output_filename"}:
                    raise AutomatedIntroductionBoundaryRuntimeError(
                        f"Introduction Boundary mapping does not define required field {key}"
                    )
                continue
            node = prompt.get(target[0])
            if not isinstance(node, dict):
                raise AutomatedIntroductionBoundaryRuntimeError(
                    f"Introduction Boundary mapping references missing node {target[0]}"
                )
            inputs = node.get("inputs")
            if not isinstance(inputs, dict):
                raise AutomatedIntroductionBoundaryRuntimeError(
                    f"Introduction Boundary workflow node {target[0]} has no inputs"
                )
            inputs[target[1]] = value
        return prompt

    @staticmethod
    def _mapping_target(mapping: dict[str, Any], key: str) -> tuple[str, str] | None:
        raw = mapping.get(key)
        if not isinstance(raw, dict):
            section = mapping.get("inputs")
            raw = section.get(key) if isinstance(section, dict) else None
        if isinstance(raw, dict):
            node = raw.get("node_id", raw.get("node"))
            field = raw.get("input", raw.get("field"))
            if node is not None and field:
                return str(node), str(field)
        if isinstance(raw, str) and "." in raw:
            node, field = raw.split(".", 1)
            return node, field
        return None

    @staticmethod
    def _read_object(path: Path, label: str) -> dict[str, Any]:
        try:
            raw = json.loads(path.expanduser().resolve(strict=True).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedIntroductionBoundaryRuntimeError(
                f"Unable to read Introduction Boundary {label}: {exc}"
            ) from exc
        if not isinstance(raw, dict):
            raise AutomatedIntroductionBoundaryRuntimeError(
                f"Introduction Boundary {label} must be a JSON object"
            )
        return raw

    @staticmethod
    def _seed(request: IntroductionBoundarySynthesisRequest) -> int:
        return int(request.fingerprint[:8], 16) & 0x7FFFFFFF

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class _BoundaryVisionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    existing_composition_preserved: bool
    introduced_assets_present: bool
    introduced_identity_matches_reference: bool
    no_unapproved_assets: bool
    camera_and_environment_preserved: bool
    confidence: int = Field(ge=0, le=100)
    findings: tuple[str, ...] = ()


class OpenAIIntroductionBoundaryValidator:
    """Vision validation for exception-based human review of generated boundaries."""

    validator_id = "openai.introduction-boundary-validator.v1"

    def __init__(self, *, api_key: str, model: str, minimum_confidence: int = 85) -> None:
        if not api_key.strip() or not model.strip():
            raise ValueError("OpenAI boundary validation requires api_key and model")
        if not 0 <= minimum_confidence <= 100:
            raise ValueError("minimum_confidence must be between 0 and 100")
        try:
            openai_module = import_module("openai")
            client_type = openai_module.OpenAI
        except (ImportError, AttributeError) as exc:
            raise AutomatedIntroductionBoundaryRuntimeError(
                'Install the VSCS AI dependency with: python -m pip install "openai>=1.68"'
            ) from exc
        self._client: Any = client_type(api_key=api_key)
        self.model = model
        self.minimum_confidence = minimum_confidence

    def validate(
        self,
        request: IntroductionBoundarySynthesisRequest,
        result: IntroductionBoundarySynthesisResult,
    ) -> IntroductionBoundaryValidationResult:
        reference_paths = self._reference_manifest_paths(request)
        content: list[dict[str, object]] = [
            {
                "type": "input_text",
                "text": (
                    "Compare the exact preceding frame with the synthesized next frame. "
                    f"Only these governed assets may be introduced now: {', '.join(request.introduced_asset_ids)}. "
                    "All existing subjects, camera, environment, lighting, scale and spatial layout "
                    "must remain continuous. Reject duplicates, identity drift, extra people/assets, "
                    "or missing introduced assets."
                ),
            },
            {
                "type": "input_text",
                "text": "Preceding source-boundary frame:",
            },
            {"type": "input_image", "image_url": self._data_url(request.source_boundary_image_path), "detail": "high"},
            {
                "type": "input_text",
                "text": "Synthesized target Introduction Keyframe:",
            },
            {"type": "input_image", "image_url": self._data_url(result.image_path), "detail": "high"},
        ]
        for reference_id, path in zip(
            request.introduced_reference_ids,
            reference_paths,
            strict=True,
        ):
            content.extend(
                (
                    {
                        "type": "input_text",
                        "text": f"Governed canonical reference for introduced identity {reference_id}:",
                    },
                    {"type": "input_image", "image_url": self._data_url(path), "detail": "high"},
                )
            )
        instructions = (
            "You are the VSCS automated Introduction Boundary validator. Evaluate conservatively "
            "from visible evidence only. The source frame is the required continuity baseline. "
            "The target frame must preserve the entire existing composition while introducing only "
            "the explicitly governed new assets. Canonical reference images define the introduced "
            "asset identity. Return false for any check that is not visually supported."
        )
        try:
            response = self._client.responses.parse(
                model=self.model,
                instructions=instructions,
                input=[{"role": "user", "content": content}],
                text_format=_BoundaryVisionDecision,
            )
            decision = cast(_BoundaryVisionDecision | None, response.output_parsed)
        except Exception as exc:
            raise AutomatedIntroductionBoundaryRuntimeError(
                f"Automated Introduction Boundary validation failed: {exc}"
            ) from exc
        if decision is None:
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Automated Introduction Boundary validator returned no structured decision"
            )
        checks = (
            ("existing_composition_preserved", decision.existing_composition_preserved),
            ("introduced_assets_present", decision.introduced_assets_present),
            ("introduced_identity_matches_reference", decision.introduced_identity_matches_reference),
            ("no_unapproved_assets", decision.no_unapproved_assets),
            ("camera_and_environment_preserved", decision.camera_and_environment_preserved),
        )
        failed = tuple(name for name, passed in checks if not passed)
        findings = tuple((*failed, *decision.findings))
        passed = not failed and decision.confidence >= self.minimum_confidence
        if not passed and decision.confidence < self.minimum_confidence:
            findings = (*findings, f"confidence_below_{self.minimum_confidence}")
        return IntroductionBoundaryValidationResult(
            passed=passed,
            checks=tuple(name for name, _ in checks),
            findings=findings,
            validator_id=f"{self.validator_id}:{self.model}:{decision.confidence}",
        )

    @staticmethod
    def _reference_manifest_paths(
        request: IntroductionBoundarySynthesisRequest,
    ) -> tuple[Path, ...]:
        manifest = (
            request.source_boundary_image_path.parent
            / "reference_paths.json"
        )
        if not manifest.is_file():
            # Orchestrator normally writes the manifest beside the automated boundary working set.
            manifest = (
                request.source_boundary_image_path.parents[0]
                / "reference_paths.json"
            )
        if not manifest.is_file():
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Governed introduced-reference path manifest is unavailable for validation"
            )
        try:
            raw = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise AutomatedIntroductionBoundaryRuntimeError(
                f"Cannot read introduced-reference path manifest: {exc}"
            ) from exc
        values = raw.get("introduced_reference_paths") if isinstance(raw, dict) else None
        if not isinstance(values, list):
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Introduced-reference path manifest is invalid"
            )
        paths = tuple(Path(str(value)).expanduser().resolve(strict=True) for value in values)
        if len(paths) != len(request.introduced_reference_ids):
            raise AutomatedIntroductionBoundaryRuntimeError(
                "Introduced-reference path count does not match governed reference authority"
            )
        return paths

    @staticmethod
    def _data_url(path: Path) -> str:
        candidate = Path(path).expanduser().resolve(strict=True)
        media_type = mimetypes.guess_type(candidate.name)[0] or "image/png"
        encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
        return f"data:{media_type};base64,{encoded}"
