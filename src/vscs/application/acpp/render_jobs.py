"""Compile ACPP packages and prompts into renderer-neutral render jobs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

from .models import ClipProductionPackage, RenderQualityMode, SeedPolicy
from .prompt_compiler import CompiledProductionPrompt
from .resolution import ACPPResolutionResult
from .serialization import ACPPSerializer


class RenderJobCompilationError(ValueError):
    """Raised when an ACPP cannot be compiled into a render job."""


class RenderCapability(StrEnum):
    """Provider-neutral capability required from a renderer."""

    TEXT_TO_VIDEO = "text_to_video"
    IMAGE_TO_VIDEO = "image_to_video"
    START_FRAME_CONDITIONING = "start_frame_conditioning"
    END_FRAME_CONDITIONING = "end_frame_conditioning"
    CANONICAL_REFERENCE_CONDITIONING = "canonical_reference_conditioning"
    NEGATIVE_PROMPT = "negative_prompt"
    DETERMINISTIC_SEED = "deterministic_seed"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Renderer-neutral retry instructions for one job."""

    maximum_attempts: int = 3
    backoff_seconds: float = 5.0
    retry_on_timeout: bool = True
    retry_on_provider_error: bool = True

    def __post_init__(self) -> None:
        if self.maximum_attempts < 1:
            raise ValueError("maximum_attempts must be at least 1")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds must not be negative")


@dataclass(frozen=True, slots=True)
class RenderInputReference:
    """One canonical or continuity reference consumed by a render job."""

    reference_id: str
    role: str


@dataclass(frozen=True, slots=True)
class RenderJob:
    """Complete renderer-neutral execution contract for one clip."""

    job_id: str
    clip_id: str
    width: int
    height: int
    frames_per_second: int
    frame_count: int
    quality_mode: RenderQualityMode
    seed_policy: SeedPolicy
    fixed_seed: int | None
    positive_prompt: str
    negative_prompt: str
    input_references: tuple[RenderInputReference, ...]
    start_reference_id: str | None
    end_reference_id: str | None
    output_path: str
    dependencies: tuple[str, ...]
    retry_policy: RetryPolicy
    required_capabilities: tuple[RenderCapability, ...]
    package_checksum: str
    prompt_checksum: str
    schema_version: str = "1.0"
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class RenderJobCompilerConfig:
    """Policy controlling render-job compilation."""

    schema_version: str = "1.0"
    retry_policy: RetryPolicy = RetryPolicy()
    require_resolved_package: bool = True

    def __post_init__(self) -> None:
        if not self.schema_version.strip():
            raise ValueError("schema_version must not be empty")


class RenderJobCompiler:
    """Compile resolved ACPPs and compiled prompts into render jobs."""

    def __init__(
        self,
        config: RenderJobCompilerConfig | None = None,
        serializer: ACPPSerializer | None = None,
    ) -> None:
        self.config = config or RenderJobCompilerConfig()
        self.serializer = serializer or ACPPSerializer()

    def compile(
        self,
        resolution: ACPPResolutionResult,
        prompt: CompiledProductionPrompt,
    ) -> RenderJob:
        """Compile one renderer-neutral job."""
        if self.config.require_resolved_package and not resolution.passed:
            raise RenderJobCompilationError(
                "Cannot compile a render job from failed resource resolution"
            )
        package = resolution.package
        if prompt.clip_id != package.identity.clip_id:
            raise RenderJobCompilationError(
                "Compiled prompt clip ID does not match the ACPP clip ID"
            )
        if not prompt.positive_prompt.strip():
            raise RenderJobCompilationError("Positive prompt must not be empty")

        references = self._input_references(package, prompt)
        capabilities = self._required_capabilities(package, prompt)
        package_checksum = self.serializer.checksum(package)
        job_id = f"JOB-{package.identity.clip_id}"
        metadata = tuple(sorted(package.metadata.items()))
        return RenderJob(
            job_id=job_id,
            clip_id=package.identity.clip_id,
            width=package.render.width,
            height=package.render.height,
            frames_per_second=package.render.frames_per_second,
            frame_count=package.render.frame_count,
            quality_mode=package.render.quality_mode,
            seed_policy=package.render.seed_policy,
            fixed_seed=package.render.fixed_seed,
            positive_prompt=prompt.positive_prompt,
            negative_prompt=prompt.negative_prompt,
            input_references=references,
            start_reference_id=prompt.start_reference_id,
            end_reference_id=prompt.end_reference_id,
            output_path=package.output.relative_path,
            dependencies=package.dependencies,
            retry_policy=self.config.retry_policy,
            required_capabilities=capabilities,
            package_checksum=package_checksum,
            prompt_checksum=prompt.checksum,
            schema_version=self.config.schema_version,
            metadata=metadata,
        )

    def checksum(self, job: RenderJob) -> str:
        """Return a deterministic checksum for one render job."""
        payload = {
            "job_id": job.job_id,
            "clip_id": job.clip_id,
            "schema_version": job.schema_version,
            "width": job.width,
            "height": job.height,
            "frames_per_second": job.frames_per_second,
            "frame_count": job.frame_count,
            "quality_mode": job.quality_mode.value,
            "seed_policy": job.seed_policy.value,
            "fixed_seed": job.fixed_seed,
            "positive_prompt": job.positive_prompt,
            "negative_prompt": job.negative_prompt,
            "input_references": [
                {"reference_id": item.reference_id, "role": item.role}
                for item in job.input_references
            ],
            "start_reference_id": job.start_reference_id,
            "end_reference_id": job.end_reference_id,
            "output_path": job.output_path,
            "dependencies": list(job.dependencies),
            "retry_policy": {
                "maximum_attempts": job.retry_policy.maximum_attempts,
                "backoff_seconds": job.retry_policy.backoff_seconds,
                "retry_on_timeout": job.retry_policy.retry_on_timeout,
                "retry_on_provider_error": job.retry_policy.retry_on_provider_error,
            },
            "required_capabilities": [
                capability.value for capability in job.required_capabilities
            ],
            "package_checksum": job.package_checksum,
            "prompt_checksum": job.prompt_checksum,
            "metadata": list(job.metadata),
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _input_references(
        package: ClipProductionPackage,
        prompt: CompiledProductionPrompt,
    ) -> tuple[RenderInputReference, ...]:
        references: list[RenderInputReference] = [
            RenderInputReference(reference_id=value, role="canonical")
            for value in prompt.canonical_reference_ids
        ]
        if prompt.start_reference_id:
            references.append(
                RenderInputReference(
                    reference_id=prompt.start_reference_id,
                    role="start_frame",
                )
            )
        if prompt.end_reference_id:
            references.append(
                RenderInputReference(
                    reference_id=prompt.end_reference_id,
                    role="end_frame",
                )
            )
        unique = {
            (item.reference_id, item.role): item
            for item in references
            if item.reference_id.strip()
        }
        return tuple(unique.values())

    @staticmethod
    def _required_capabilities(
        package: ClipProductionPackage,
        prompt: CompiledProductionPrompt,
    ) -> tuple[RenderCapability, ...]:
        capabilities = [RenderCapability.TEXT_TO_VIDEO]
        if prompt.canonical_reference_ids:
            capabilities.extend(
                (
                    RenderCapability.IMAGE_TO_VIDEO,
                    RenderCapability.CANONICAL_REFERENCE_CONDITIONING,
                )
            )
        if prompt.start_reference_id:
            capabilities.append(RenderCapability.START_FRAME_CONDITIONING)
        if prompt.end_reference_id:
            capabilities.append(RenderCapability.END_FRAME_CONDITIONING)
        if prompt.negative_prompt:
            capabilities.append(RenderCapability.NEGATIVE_PROMPT)
        if package.render.seed_policy is not SeedPolicy.RANDOM:
            capabilities.append(RenderCapability.DETERMINISTIC_SEED)
        return tuple(dict.fromkeys(capabilities))
