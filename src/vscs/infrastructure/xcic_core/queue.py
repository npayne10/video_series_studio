"""Atomic XCIC queue writer used by the Core renderer."""

from __future__ import annotations

import json
from pathlib import Path

from vscs.infrastructure.xcic_core.models import XCICCoreJob


class XCICCoreQueueError(RuntimeError):
    """Raised when an XCIC queue cannot be written safely."""


class XCICCoreQueueWriter:
    """Serialize rendering jobs in the queue contract consumed by XCIC loader nodes."""

    def write(self, path: Path, jobs: tuple[XCICCoreJob, ...]) -> None:
        payload = {
            "schema_version": "1.0",
            "job_count": len(jobs),
            "jobs": [self._job_payload(job) for job in jobs],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            raise XCICCoreQueueError(f"Unable to write XCIC queue {path}: {exc}") from exc

    @staticmethod
    def _job_payload(job: XCICCoreJob) -> dict[str, object]:
        value: dict[str, object] = {
            "job_id": job.job_id,
            "asset_id": job.asset_id,
            "positive_prompt": job.positive_prompt,
            "negative_prompt": job.negative_prompt,
            "width": job.width,
            "height": job.height,
            "seed": job.seed,
            "steps": job.steps,
            "cfg": job.cfg,
            "quality_mode": job.quality_mode,
            "output": {
                "candidate_directory": str(job.candidate_directory),
                "candidate_filename": job.candidate_filename,
            },
            "candidate_directory": str(job.candidate_directory),
            "candidate_filename": job.candidate_filename,
            "metadata": job.metadata,
        }
        if job.reference_path is not None:
            value["reference_path"] = str(job.reference_path)
            value["identity_reference"] = str(job.reference_path)
        return value
