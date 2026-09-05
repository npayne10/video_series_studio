"""Durable provider-segment execution state for governed LTX production work."""

from __future__ import annotations

import hashlib
import json
import shutil
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
    render_job_id: str | None = None
    render_request_id: str | None = None
    submitted_at: str | None = None
    continuity_input_path: str | None = None
    output_path: str | None = None
    final_frame_path: str | None = None
    observed_frame_count: int | None = None
    observed_frames_per_second: float | None = None
    observed_width: int | None = None
    observed_height: int | None = None
    error_message: str | None = None
    updated_at: str = ""

    def with_state(self, state: str, **changes: object) -> SegmentExecutionRecord:
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
            if all(record.state == "PLANNED" for record in existing):
                return existing
            self._archive_current_history(task_id, package_fingerprint, existing)
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
        directory = self.package_directory(task_id, package_fingerprint)
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
        directory = self.package_directory(record.task_id, record.package_fingerprint)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{record.segment_id}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(asdict(record), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path

    def package_directory(self, task_id: str, package_fingerprint: str) -> Path:
        identity = hashlib.sha256(f"{task_id}:{package_fingerprint}".encode()).hexdigest()[:16]
        return self.root / task_id / identity

    def history_directories(self, task_id: str, package_fingerprint: str) -> tuple[Path, ...]:
        history = self.package_directory(task_id, package_fingerprint) / "history"
        if not history.is_dir():
            return ()
        return tuple(sorted(path for path in history.iterdir() if path.is_dir()))

    def _archive_current_history(
        self,
        task_id: str,
        package_fingerprint: str,
        records: tuple[SegmentExecutionRecord, ...],
    ) -> None:
        directory = self.package_directory(task_id, package_fingerprint)
        execution_ids = {
            record.provider_execution_id
            for record in records
            if record.provider_execution_id is not None
        }
        if len(execution_ids) == 1:
            label = next(iter(execution_ids))
        else:
            label = max((record.updated_at for record in records), default="unbound")
        identity = hashlib.sha256(label.encode()).hexdigest()[:16]
        history_root = directory / "history"
        history_root.mkdir(parents=True, exist_ok=True)
        destination = history_root / identity
        suffix = 1
        while destination.exists():
            destination = history_root / f"{identity}-{suffix:02d}"
            suffix += 1
        destination.mkdir(parents=True)
        for path in tuple(directory.iterdir()):
            if path.name == "history":
                continue
            shutil.move(str(path), str(destination / path.name))
