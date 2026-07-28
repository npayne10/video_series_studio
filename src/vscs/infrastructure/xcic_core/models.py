"""Stable contracts for the XCIC Core Rendering Library v1.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class XCICCoreWorkflow:
    """Editable/API workflow pair and loader-node contract."""

    workflow_id: str
    editable_path: Path
    compiled_path: Path
    loader_class: str
    queue_file_path: Path
    quality_mode: str = "standard"
    version: str = "1.0"


@dataclass(frozen=True, slots=True)
class XCICCoreJob:
    """One rendering job represented in an XCIC queue file."""

    job_id: str
    asset_id: str
    positive_prompt: str
    negative_prompt: str
    candidate_directory: Path
    candidate_filename: str
    width: int
    height: int
    seed: int
    steps: int = 4
    cfg: float = 1.0
    quality_mode: str = "standard"
    reference_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class XCICCoreResult:
    """Verified output returned by the XCIC Core renderer."""

    job: XCICCoreJob
    output_path: Path
    prompt_id: str
    workflow_id: str
    workflow_version: str
    history: dict[str, Any]
