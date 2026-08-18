"""Durable JSON persistence for ProductionSchedule revisions and reviews."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from vscs.application.production_tasks.models import ProductionCapability, ProductionTaskPriority
from vscs.application.production_tasks.schedule_records import (
    ProductionScheduleRepository,
    ProductionScheduleReviewDecision,
    ProductionScheduleReviewRecord,
    ProductionScheduleSnapshot,
)
from vscs.application.production_tasks.scheduler import (
    ProductionSchedule,
    ProductionScheduleAssignment,
    ProductionScheduleDeferral,
    ProductionSchedulingDeferralReason,
)


class JsonProductionScheduleRepository(ProductionScheduleRepository):
    """Persist immutable schedule revisions and append-only review history as JSON."""

    SCHEMA_VERSION = "1.0"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def save_snapshot(self, snapshot: ProductionScheduleSnapshot) -> ProductionScheduleSnapshot:
        """Persist one new revision without overwriting an existing snapshot."""
        path = self._snapshot_path(snapshot.schedule_id, snapshot.revision)
        if path.exists():
            raise RuntimeError(
                f"ProductionSchedule revision already exists: {snapshot.schedule_id} r{snapshot.revision}"
            )
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "snapshot": self._snapshot_to_payload(snapshot),
        }
        self._write_atomic(path, payload)
        return snapshot

    def get_snapshot(self, schedule_id: str, revision: int) -> ProductionScheduleSnapshot | None:
        """Return one exact schedule revision."""
        if revision < 1:
            return None
        path = self._snapshot_path(schedule_id.strip(), revision)
        if not path.exists():
            return None
        return self._read_snapshot(path)

    def history_for_production(
        self,
        production_id: str,
    ) -> tuple[ProductionScheduleSnapshot, ...]:
        """Return all revisions for one production in revision order."""
        normalized = production_id.strip()
        snapshots = tuple(
            snapshot
            for path in sorted(self.root.glob("*/revision-*.json"))
            if self.root.exists()
            if (snapshot := self._read_snapshot(path)).production_id == normalized
        )
        return tuple(sorted(snapshots, key=lambda item: item.revision))

    def latest_for_production(self, production_id: str) -> ProductionScheduleSnapshot | None:
        """Return the highest persisted revision for one production."""
        history = self.history_for_production(production_id)
        return history[-1] if history else None

    def append_review(
        self,
        review: ProductionScheduleReviewRecord,
    ) -> ProductionScheduleReviewRecord:
        """Append one immutable human review decision."""
        path = self._reviews_path(review.schedule_id)
        records = self._read_reviews(path)
        if any(record.revision == review.revision for record in records):
            raise RuntimeError(
                f"ProductionSchedule revision already reviewed: {review.schedule_id} r{review.revision}"
            )
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "records": [self._review_to_payload(record) for record in (*records, review)],
        }
        self._write_atomic(path, payload)
        return review

    def reviews(
        self,
        schedule_id: str,
        revision: int,
    ) -> tuple[ProductionScheduleReviewRecord, ...]:
        """Return reviews for one exact schedule revision."""
        path = self._reviews_path(schedule_id.strip())
        return tuple(record for record in self._read_reviews(path) if record.revision == revision)

    def _read_snapshot(self, path: Path) -> ProductionScheduleSnapshot:
        payload = self._read_payload(path)
        raw = payload.get("snapshot")
        if not isinstance(raw, dict):
            raise RuntimeError(f"Invalid ProductionSchedule snapshot payload: {path}")
        return self._snapshot_from_payload(raw)

    def _read_reviews(self, path: Path) -> tuple[ProductionScheduleReviewRecord, ...]:
        if not path.exists():
            return ()
        payload = self._read_payload(path)
        raw_records = payload.get("records", [])
        if not isinstance(raw_records, list):
            raise RuntimeError(f"Invalid ProductionSchedule review payload: {path}")
        return tuple(self._review_from_payload(raw) for raw in raw_records)

    def _read_payload(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Unable to read ProductionSchedule data {path}: {exc}") from exc
        if not isinstance(payload, dict) or payload.get("schema_version") != self.SCHEMA_VERSION:
            raise RuntimeError(f"Unsupported ProductionSchedule repository schema: {path}")
        return payload

    @staticmethod
    def _snapshot_to_payload(snapshot: ProductionScheduleSnapshot) -> dict[str, Any]:
        schedule = snapshot.schedule
        return {
            "schedule_id": snapshot.schedule_id,
            "production_id": snapshot.production_id,
            "revision": snapshot.revision,
            "fingerprint": snapshot.fingerprint,
            "created_at": snapshot.created_at.isoformat(),
            "schedule": {
                "production_id": schedule.production_id,
                "assignments": [
                    {
                        "task_id": item.task_id,
                        "resource_id": item.resource_id,
                        "priority": int(item.priority),
                        "required_capabilities": [
                            capability.value for capability in item.required_capabilities
                        ],
                    }
                    for item in schedule.assignments
                ],
                "deferrals": [
                    {
                        "task_id": item.task_id,
                        "reason": item.reason.value,
                        "resource_ids": list(item.resource_ids),
                    }
                    for item in schedule.deferrals
                ],
                "ignored_task_ids": list(schedule.ignored_task_ids),
            },
        }

    @staticmethod
    def _snapshot_from_payload(raw: dict[str, Any]) -> ProductionScheduleSnapshot:
        schedule_raw = raw["schedule"]
        if not isinstance(schedule_raw, dict):
            raise TypeError("schedule must be an object")
        assignments_raw = schedule_raw.get("assignments", [])
        deferrals_raw = schedule_raw.get("deferrals", [])
        if not isinstance(assignments_raw, list) or not isinstance(deferrals_raw, list):
            raise TypeError("schedule assignments and deferrals must be arrays")
        schedule = ProductionSchedule(
            production_id=str(schedule_raw["production_id"]),
            assignments=tuple(
                ProductionScheduleAssignment(
                    task_id=str(item["task_id"]),
                    resource_id=str(item["resource_id"]),
                    priority=ProductionTaskPriority(int(item["priority"])),
                    required_capabilities=tuple(
                        ProductionCapability(str(value))
                        for value in item.get("required_capabilities", [])
                    ),
                )
                for item in assignments_raw
            ),
            deferrals=tuple(
                ProductionScheduleDeferral(
                    task_id=str(item["task_id"]),
                    reason=ProductionSchedulingDeferralReason(str(item["reason"])),
                    resource_ids=tuple(str(value) for value in item.get("resource_ids", [])),
                )
                for item in deferrals_raw
            ),
            ignored_task_ids=tuple(
                str(value) for value in schedule_raw.get("ignored_task_ids", [])
            ),
        )
        return ProductionScheduleSnapshot(
            schedule_id=str(raw["schedule_id"]),
            production_id=str(raw["production_id"]),
            revision=int(raw["revision"]),
            fingerprint=str(raw["fingerprint"]),
            schedule=schedule,
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )

    @staticmethod
    def _review_to_payload(review: ProductionScheduleReviewRecord) -> dict[str, Any]:
        return {
            "schedule_id": review.schedule_id,
            "production_id": review.production_id,
            "revision": review.revision,
            "fingerprint": review.fingerprint,
            "decision": review.decision.value,
            "reviewed_by": review.reviewed_by,
            "notes": review.notes,
            "reviewed_at": review.reviewed_at.isoformat(),
        }

    @staticmethod
    def _review_from_payload(raw: object) -> ProductionScheduleReviewRecord:
        if not isinstance(raw, dict):
            raise TypeError("review record must be an object")
        return ProductionScheduleReviewRecord(
            schedule_id=str(raw["schedule_id"]),
            production_id=str(raw["production_id"]),
            revision=int(raw["revision"]),
            fingerprint=str(raw["fingerprint"]),
            decision=ProductionScheduleReviewDecision(str(raw["decision"])),
            reviewed_by=str(raw["reviewed_by"]),
            notes=str(raw["notes"]),
            reviewed_at=datetime.fromisoformat(str(raw["reviewed_at"])),
        )

    def _snapshot_path(self, schedule_id: str, revision: int) -> Path:
        normalized = self._safe_schedule_id(schedule_id)
        return self.root / normalized / f"revision-{revision:06d}.json"

    def _reviews_path(self, schedule_id: str) -> Path:
        normalized = self._safe_schedule_id(schedule_id)
        return self.root / normalized / "reviews.json"

    @staticmethod
    def _safe_schedule_id(schedule_id: str) -> str:
        normalized = schedule_id.strip()
        if not normalized or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
            for character in normalized
        ):
            raise RuntimeError(f"Invalid ProductionSchedule identity: {schedule_id!r}")
        return normalized

    @staticmethod
    def _write_atomic(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise RuntimeError(f"Unable to persist ProductionSchedule data {path}: {exc}") from exc
