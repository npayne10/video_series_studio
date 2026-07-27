"""XCIC rendering engine models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class XCICWorkflowKind(StrEnum):
    """Supported XCIC workflow families."""

    TEXT_TO_IMAGE = "text_to_image"
    REFERENCE_IMAGE = "reference_image"


@dataclass(frozen=True, slots=True)
class XCICWorkflowDefinition:
    """Registered ComfyUI API workflow and mapping/profile contract."""

    name: str
    kind: XCICWorkflowKind
    api_workflow_path: Path
    mapping_path: Path
    profile_path: Path
    output_directory: Path
    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class XCICGenerationJob:
    """One independently submitted XCIC generation request."""

    job_id: str
    asset_id: str
    positive_prompt: str
    negative_prompt: str
    width: int
    height: int
    seed: int
    steps: int
    cfg: float
    candidate_directory: Path
    candidate_filename: str
    reference_path: Path | None = None
    quality_mode: str = "standard"
    enable_turbo_mode: bool = True


@dataclass(frozen=True, slots=True)
class XCICRenderedFile:
    """A completed output returned by the XCIC engine."""

    path: Path
    job: XCICGenerationJob
    workflow_name: str
    workflow_version: str
