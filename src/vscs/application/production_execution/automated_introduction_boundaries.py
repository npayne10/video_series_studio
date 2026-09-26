"""Provider-neutral automation contracts for timed asset introduction boundaries.

Phase 20.18.2.3.6 removes routine manual image preparation from dynamic Shots.
The application layer decides *what* must happen and persists explicit provenance;
provider adapters decide *how* a boundary image is synthesized.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .introduction_keyframes import IntroductionKeyframeRequirement


class AutomatedIntroductionBoundaryError(RuntimeError):
    """Raised when automated introduction-boundary governance cannot proceed safely."""


class IntroductionBoundaryStrategy(StrEnum):
    """Provider-neutral execution strategy for one timed introduction."""

    PROVIDER_NATIVE = "provider_native_timed_reference"
    SYNTHESIZED_KEYFRAME = "synthesized_introduction_keyframe"
    MANUAL_FALLBACK = "manual_fallback"


class IntroductionBoundaryAutomationState(StrEnum):
    """Durable automation state for one internal introduction boundary."""

    PLANNED = "planned"
    SOURCE_REQUIRED = "source_required"
    SYNTHESIS_REQUIRED = "synthesis_required"
    VALIDATION_REQUIRED = "validation_required"
    READY = "ready"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class IntroductionBoundaryProviderCapabilities:
    """Capabilities needed to select an automated introduction strategy."""

    provider_id: str
    timed_reference_injection: bool = False
    introduction_frame_synthesis: bool = False
    first_frame_i2v: bool = True

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise AutomatedIntroductionBoundaryError("Provider capability requires provider_id")


@dataclass(frozen=True, slots=True)
class IntroductionBoundarySynthesisRequest:
    """Exact provider-neutral request for one generated target Introduction Keyframe."""

    shot_id: str
    requirement_id: str
    boundary_id: str
    source_global_frame_index: int
    target_global_frame_index: int
    source_boundary_image_path: Path
    introduced_asset_ids: tuple[str, ...]
    introduced_reference_ids: tuple[str, ...]
    active_asset_ids: tuple[str, ...]
    active_reference_ids: tuple[str, ...]
    frame_state_reference_ids: tuple[str, ...]
    width: int
    height: int
    prompt: str
    negative_prompt: str

    def __post_init__(self) -> None:
        if not self.shot_id.strip() or not self.requirement_id.strip() or not self.boundary_id.strip():
            raise AutomatedIntroductionBoundaryError(
                "Introduction-boundary synthesis request requires governed identities"
            )
        if self.source_global_frame_index < 0:
            raise AutomatedIntroductionBoundaryError("Source boundary frame cannot be negative")
        if self.target_global_frame_index != self.source_global_frame_index + 1:
            raise AutomatedIntroductionBoundaryError(
                "Introduction target frame must immediately follow its source boundary frame"
            )
        if not self.introduced_asset_ids or not self.introduced_reference_ids:
            raise AutomatedIntroductionBoundaryError(
                "Automated introduction synthesis requires introduced assets and references"
            )
        if not set(self.introduced_reference_ids).issubset(set(self.active_reference_ids)):
            raise AutomatedIntroductionBoundaryError(
                "Introduced references must be active at the target frame"
            )
        if self.width <= 0 or self.height <= 0:
            raise AutomatedIntroductionBoundaryError(
                "Introduction-boundary target dimensions must be positive"
            )

    @property
    def fingerprint(self) -> str:
        payload = {
            "shot_id": self.shot_id,
            "requirement_id": self.requirement_id,
            "boundary_id": self.boundary_id,
            "source_global_frame_index": self.source_global_frame_index,
            "target_global_frame_index": self.target_global_frame_index,
            "source_boundary_image_path": str(self.source_boundary_image_path),
            "introduced_asset_ids": list(self.introduced_asset_ids),
            "introduced_reference_ids": list(self.introduced_reference_ids),
            "active_asset_ids": list(self.active_asset_ids),
            "active_reference_ids": list(self.active_reference_ids),
            "frame_state_reference_ids": list(self.frame_state_reference_ids),
            "width": self.width,
            "height": self.height,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class IntroductionBoundarySynthesisResult:
    """Provider output before it becomes governed Introduction Keyframe authority."""

    image_path: Path
    provider_id: str
    provider_job_id: str
    request_fingerprint: str
    output_sha256: str

    def __post_init__(self) -> None:
        if not self.provider_id.strip() or not self.provider_job_id.strip():
            raise AutomatedIntroductionBoundaryError(
                "Automated synthesis result requires provider provenance"
            )
        if not self.request_fingerprint.strip() or not self.output_sha256.strip():
            raise AutomatedIntroductionBoundaryError(
                "Automated synthesis result requires request/output fingerprints"
            )


@dataclass(frozen=True, slots=True)
class IntroductionBoundaryValidationResult:
    """Automated validation decision for a synthesized introduction frame."""

    passed: bool
    checks: tuple[str, ...]
    findings: tuple[str, ...] = ()
    validator_id: str = "vscs.introduction-boundary-validator.v1"

    def __post_init__(self) -> None:
        if not self.validator_id.strip():
            raise AutomatedIntroductionBoundaryError("Boundary validation requires validator_id")
        if self.passed and self.findings:
            raise AutomatedIntroductionBoundaryError(
                "Passing introduction-boundary validation cannot contain blocking findings"
            )


class IntroductionBoundarySynthesizer(Protocol):
    """Provider adapter capable of generating one exact target introduction image."""

    provider_id: str

    def synthesize(
        self,
        request: IntroductionBoundarySynthesisRequest,
    ) -> IntroductionBoundarySynthesisResult: ...


class IntroductionBoundaryValidator(Protocol):
    """Automated validator for synthesized introduction frames."""

    validator_id: str

    def validate(
        self,
        request: IntroductionBoundarySynthesisRequest,
        result: IntroductionBoundarySynthesisResult,
    ) -> IntroductionBoundaryValidationResult: ...


@dataclass(frozen=True, slots=True)
class AutomatedSpanExecutionResult:
    """One normalized internal-span provider output with complete provider provenance."""

    span_sequence_number: int
    package_path: Path
    output_path: Path
    provider_id: str
    provider_job_id: str

    def __post_init__(self) -> None:
        if self.span_sequence_number <= 0:
            raise AutomatedIntroductionBoundaryError("Span sequence number must be positive")
        if not self.provider_id.strip() or not self.provider_job_id.strip():
            raise AutomatedIntroductionBoundaryError(
                "Automated span execution requires provider provenance"
            )


class TimedSpanExecutor(Protocol):
    """Execute exactly one current governed internal-span package."""

    provider_id: str

    def execute(
        self,
        package_path: Path,
        *,
        span_sequence_number: int,
    ) -> AutomatedSpanExecutionResult: ...


class IntroductionBoundaryAutomationPlanner:
    """Choose the least-manual safe strategy from declared provider capabilities."""

    @staticmethod
    def choose(
        capabilities: IntroductionBoundaryProviderCapabilities,
    ) -> IntroductionBoundaryStrategy:
        if capabilities.timed_reference_injection:
            return IntroductionBoundaryStrategy.PROVIDER_NATIVE
        if capabilities.introduction_frame_synthesis and capabilities.first_frame_i2v:
            return IntroductionBoundaryStrategy.SYNTHESIZED_KEYFRAME
        return IntroductionBoundaryStrategy.MANUAL_FALLBACK

    @staticmethod
    def prompt(requirement: IntroductionKeyframeRequirement) -> tuple[str, str]:
        introduced = ", ".join(requirement.introduced_asset_ids)
        positive = (
            "Preserve the exact preceding composition, camera, lighting, environment, scale, "
            "spatial layout, and all already-visible governed identities. Introduce only the "
            f"governed asset(s) {introduced} at this exact target frame. Keep every existing "
            "subject unchanged and physically continuous with the preceding frame."
        )
        negative = (
            "early introduction, missing introduced asset, duplicate person, duplicate asset, "
            "identity drift, changed camera, changed lighting, changed environment, changed scale, "
            "repositioned existing subject, extra person, extra asset, text, watermark"
        )
        return positive, negative
