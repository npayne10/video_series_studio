"""Durable provider-segment execution state for governed LTX production work."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SegmentExecutionRecord:
    task_id: str
    package_fingerprint: str
    segment_id: str
    segment_index: int
    frame_count: int
    start_frame: int
    end_frame: int
    seed: int
    state: str
    provider_execution_id: str | None = None
    provider_prompt_id: str | None = None
    continuity_input_path: str | None = None
    output_path: str | None = None
    final_frame_path: str | None = None
    error_message: str | None = None
    updated_at: str = ""

    def with_state(self, state: str, **changes: object) -> "SegmentExecutionRecord":
        return replace(
            self,
            state=state,
            updated_at=datetime.now(UTC).isoformat(),
            **changes,
        )


class SegmentExecutionStore:
    """Append-safe deterministic storage for per-segment provider execution provenance."""

    ROOT = Path(".vscs") / "provider_executions" / "segments"

    def __init__(self, project_directory: Path) -> None:
        self.project_directory = Path(project_directory)
        self.root = self.project_directory / self.ROOT

    def initialize(
        self,
        *,
        task_id: str,
        package_fingerprint: str,
        segments: list[dict[str, Any]],
    ) -> tuple[SegmentExecutionRecord, ...]:
        existing = self.list_for_package(task_id, package_fingerprint)
        if existing:
            return existing
        records = tuple(
            SegmentExecutionRecord(
                task_id=task_id,
                package_fingerprint=package_fingerprint,
                segment_id=str(item["segment_id"]),
                segment_index=int(item["index"]),
                frame_count=int(item["frame_count"]),
                start_frame=int(item["start_frame"]),
                end_frame=int(item["end_frame"]),
                seed=int(item["seed"]),
                state="PLANNED",
                updated_at=datetime.now(UTC).isoformat(),
            )
            for item in segments
        )
        for record in records:
            self.save(record)
        return records

    def list_for_package(
        self, task_id: str, package_fingerprint: str
    ) -> tuple[SegmentExecutionRecord, ...]:
        directory = self._package_directory(task_id, package_fingerprint)
        if not directory.is_dir():
            return ()
        records: list[SegmentExecutionRecord] = []
        for path in sorted(directory.glob("SEG-*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(raw, dict):
                records.append(SegmentExecutionRecord(**raw))
        return tuple(sorted(records, key=lambda item: item.segment_index))

    def save(self, record: SegmentExecutionRecord) -> Path:
        directory = self._package_directory(record.task_id, record.package_fingerprint)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{record.segment_id}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(asdict(record), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def _package_directory(self, task_id: str, package_fingerprint: str) -> Path:
        identity = hashlib.sha256(f"{task_id}:{package_fingerprint}".encode("utf-8")).hexdigest()[:16]
        return self.root / task_id / identity
