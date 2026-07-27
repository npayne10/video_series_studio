"""XCIC queue serialization compatible with the custom ComfyUI loader nodes."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from vscs.infrastructure.xcic.models import XCICGenerationJob


class XCICQueueError(RuntimeError):
    """Raised when an XCIC queue cannot be written safely."""


class XCICQueueWriter:
    """Write an atomic queue document for XCICQueueJobLoader nodes."""

    def write(self, path: Path, jobs: tuple[XCICGenerationJob, ...]) -> Path:
        if not jobs:
            raise XCICQueueError("At least one XCIC generation job is required")
        path = path.expanduser().resolve(strict=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "vscs.xcic.queue/1.0",
            "created_at": datetime.now(UTC).isoformat(),
            "jobs": [self._job_payload(job) for job in jobs],
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            raise XCICQueueError(f"Unable to write XCIC queue {path}: {exc}") from exc
        return path

    @staticmethod
    def _job_payload(job: XCICGenerationJob) -> dict[str, object]:
        value = asdict(job)
        for key in ("candidate_directory", "reference_path"):
            if value[key] is not None:
                value[key] = str(value[key])
        return value
