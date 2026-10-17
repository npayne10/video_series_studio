"""Read-only per-Shot evidence inventory for Episode Assembly.

Inventory presence is not approval or permission for final assembly.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ShotEvidenceRow:
    shot_id: str
    planning: str
    media: str
    assembly: str
    production_task: str
    blockers: tuple[str, ...]


def reconcile_shot_evidence(
    required: tuple[str, ...],
    authority_blockers: tuple[str, ...],
    selections: tuple[Any, ...],
    media_records: Iterable[Any],
    tasks: Iterable[Any],
) -> tuple[ShotEvidenceRow, ...]:
    """Separate missing timeline selection from independently persisted evidence."""
    selected = {item.shot_id: item for item in selections}
    media_by_shot: dict[str, list[Any]] = {}
    for record in media_records:
        media_by_shot.setdefault(record.scope.shot_id, []).append(record)
    tasks_by_shot: dict[str, list[Any]] = {}
    for task in tasks:
        if task.shot_id:
            tasks_by_shot.setdefault(task.shot_id, []).append(task)
    rows: list[ShotEvidenceRow] = []
    for shot_id in required:
        blockers = tuple(text for text in authority_blockers if text.startswith(f"{shot_id}:"))
        media = media_by_shot.get(shot_id, [])
        approved = [
            item
            for item in media
            if item.state.value == "approved"
            and any(event.to_state.value == "approved" for event in item.governance_history)
        ]
        selection = selected.get(shot_id)
        media_status = (
            f"{len(approved)} approved / {len(media)} records"
            if approved
            else ("Exists — QC/approval pending" if media else "No media record")
        )
        assembly = "Selected" if selection is not None else "Not in timeline"
        task_records = tasks_by_shot.get(shot_id, [])
        task_status = (
            ", ".join(sorted({task.state.value for task in task_records}))
            if task_records
            else "No task record"
        )
        details = list(blockers)
        if selection is None:
            details.append("Not selected in assembly timeline")
        elif selection.media_state != "approved" or not selection.approval_evidence_ref:
            details.append("Selected media lacks approval evidence")
        if not media:
            details.append("No persisted Generated Media record")
        elif not approved:
            details.append("Generated Media exists; authoritative QC approval pending")
        rows.append(
            ShotEvidenceRow(
                shot_id,
                "Blocked" if blockers else "No Shot-level blockers",
                media_status,
                assembly,
                task_status,
                tuple(details),
            )
        )
    return tuple(rows)
