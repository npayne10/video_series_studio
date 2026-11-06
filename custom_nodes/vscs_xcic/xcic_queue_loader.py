"""ComfyUI custom node for VSCS XCIC Core queue rendering.

Contract: VSCS xcic_core.queue.XCICCoreQueueWriter schema_version 1.0.
This module depends on the Python standard library only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


class XCICQueueJobLoader:
    """Load one explicitly indexed XCIC job from the VSCS-generated queue."""

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "queue_file": ("STRING", {"default": "", "multiline": False}),
                "job_index": ("INT", {"default": 0, "min": 0, "max": 100000}),
                "quality_mode": ("STRING", {"default": "standard"}),
            }
        }

    RETURN_TYPES = (
        "STRING",
        "STRING",
        "INT",
        "INT",
        "INT",
        "INT",
        "FLOAT",
        "STRING",
        "STRING",
    )
    RETURN_NAMES = (
        "positive_prompt",
        "negative_prompt",
        "width",
        "height",
        "seed",
        "steps",
        "cfg",
        "candidate_directory",
        "candidate_filename",
    )
    FUNCTION = "load_job"
    CATEGORY = "VSCS/XCIC"

    @classmethod
    def IS_CHANGED(
        cls, queue_file: str, job_index: int, quality_mode: str = "standard"
    ) -> float:
        """Read current queue each invocation; avoid stale ComfyUI node cache."""
        return float("nan")

    @staticmethod
    def _required_text(value: object, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"XCIC queue job requires nonempty {field}")
        return value

    @staticmethod
    def _required_int(value: object, field: str, minimum: int) -> int:
        if type(value) is not int or value < minimum:
            raise ValueError(f"XCIC queue job {field} must be an integer >= {minimum}")
        return value

    @classmethod
    def load_job(
        cls, queue_file: str, job_index: int, quality_mode: str = "standard"
    ) -> tuple[str, str, int, int, int, int, float, str, str]:
        path = Path(cls._required_text(queue_file, "queue_file")).expanduser()
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Unable to read XCIC queue at {path}: {exc}") from exc
        if not isinstance(source, dict) or source.get("schema_version") != "1.0":
            raise ValueError("XCIC queue must use schema_version 1.0")
        jobs = source.get("jobs")
        if not isinstance(jobs, list) or not jobs:
            raise ValueError("XCIC queue must contain a nonempty jobs list")
        if (
            type(job_index) is not int
            or job_index < 0
            or job_index >= len(jobs)
        ):
            raise ValueError(f"XCIC queue job_index {job_index} is out of range")
        if source.get("job_count") != len(jobs):
            raise ValueError("XCIC queue job_count disagrees with jobs")
        job = jobs[job_index]
        if not isinstance(job, dict):
            raise ValueError("XCIC queue job must be a JSON object")
        if quality_mode not in {"standard", "fast", "quality"}:
            raise ValueError(f"Unsupported XCIC quality_mode: {quality_mode}")
        job_mode = job.get("quality_mode", "standard")
        if not isinstance(job_mode, str) or job_mode != quality_mode:
            raise ValueError(
                "XCIC quality_mode differs from current governed queue job"
            )

        positive = cls._required_text(job.get("positive_prompt"), "positive_prompt")
        negative = job.get("negative_prompt", "")
        if not isinstance(negative, str):
            raise ValueError("XCIC negative_prompt must be a string")
        width = cls._required_int(job.get("width"), "width", 64)
        height = cls._required_int(job.get("height"), "height", 64)
        seed = cls._required_int(job.get("seed"), "seed", 0)
        steps = cls._required_int(job.get("steps"), "steps", 1)
        cfg = job.get("cfg")
        if isinstance(cfg, bool) or not isinstance(cfg, (int, float)):
            raise ValueError("XCIC cfg must be numeric")
        cfg = float(cfg)
        if not math.isfinite(cfg) or cfg < 0:
            raise ValueError("XCIC cfg must be finite and nonnegative")

        output = job.get("output")
        if not isinstance(output, dict):
            raise ValueError("XCIC queue job requires an output object")
        directory = cls._required_text(
            output.get("candidate_directory"), "output.candidate_directory"
        )
        filename = cls._required_text(
            output.get("candidate_filename"), "output.candidate_filename"
        )
        # Reject paths that could escape the expected candidate folder.
        if (
            not Path(directory).is_absolute()
            or Path(filename).name != filename
            or Path(filename).suffix.lower() != ".png"
            or filename in {".", ".."}
        ):
            raise ValueError("XCIC output must be an absolute directory and safe PNG filename")

        return positive, negative, width, height, seed, steps, cfg, directory, filename
