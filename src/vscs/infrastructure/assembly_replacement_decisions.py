"""Immutable, content-addressed replacement decisions for Assembly Draft successors."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vscs.application.assembly_contracts import ShotSelection


class ReplacementDecisionError(ValueError):
    """Missing, malformed or mismatched operator replacement evidence."""


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ReplacementDecision:
    decision_id: str
    assembly_id: str
    predecessor_revision_id: str
    successor_revision_id: str
    predecessor_fingerprint: str
    successor_fingerprint: str
    shot_id: str
    previous_selection: ShotSelection
    replacement_selection: ShotSelection
    operator_id: str
    justification: str
    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        if self.schema_version != "1.0":
            raise ReplacementDecisionError("Unsupported replacement decision schema")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.decision_id):
            raise ReplacementDecisionError("Unsafe replacement decision ID")
        for field in (
            "assembly_id",
            "predecessor_revision_id",
            "successor_revision_id",
            "operator_id",
            "justification",
        ):
            if not getattr(self, field).strip():
                raise ReplacementDecisionError(f"{field} is required")
        for name in ("predecessor_fingerprint", "successor_fingerprint"):
            if not re.fullmatch(r"[0-9a-f]{64}", getattr(self, name)):
                raise ReplacementDecisionError(f"{name} must be SHA-256")
        if self.shot_id != self.previous_selection.shot_id:
            raise ReplacementDecisionError("Previous selection Shot mismatch")
        if self.shot_id != self.replacement_selection.shot_id:
            raise ReplacementDecisionError("Replacement selection Shot mismatch")
        if self.previous_selection == self.replacement_selection:
            raise ReplacementDecisionError("Replacement must change selection")

    @property
    def fingerprint(self) -> str:
        return _digest(asdict(self))


class JsonReplacementDecisionRepository:
    """Append-only decision evidence. Never rewrites a stored decision."""

    def __init__(self, project_directory: Path) -> None:
        self.root = Path(project_directory) / ".vscs" / "episode_assembly" / "replacement_decisions"

    def _path(self, decision_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", decision_id):
            raise ReplacementDecisionError("Unsafe replacement decision ID")
        return self.root / f"{decision_id}.json"

    def create(self, decision: ReplacementDecision) -> Path:
        path = self._path(decision.decision_id)
        if path.exists():
            raise ReplacementDecisionError("Replacement decision already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"fingerprint": decision.fingerprint, "decision": asdict(decision)}
        staged: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
            ) as stream:
                staged = Path(stream.name)
                json.dump(payload, stream, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.link(staged, path)
        except FileExistsError as exc:
            raise ReplacementDecisionError("Replacement decision already exists") from exc
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)
        return path

    def get(self, decision_id: str) -> ReplacementDecision | None:
        path = self._path(decision_id)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != {"fingerprint", "decision"}:
                raise ReplacementDecisionError("Malformed replacement envelope")
            fields = payload["decision"]
            if not isinstance(fields, dict) or set(fields) != set(
                ReplacementDecision.__dataclass_fields__
            ):
                raise ReplacementDecisionError("Malformed replacement decision fields")
            for name in ("previous_selection", "replacement_selection"):
                raw = fields[name]
                if not isinstance(raw, dict) or set(raw) != set(ShotSelection.__dataclass_fields__):
                    raise ReplacementDecisionError("Malformed decision selection")
                fields[name] = ShotSelection(
                    **{**raw, "boundary_evidence_refs": tuple(raw["boundary_evidence_refs"])}
                )
            decision = ReplacementDecision(**fields)
            if (
                decision.decision_id != decision_id
                or decision.fingerprint != payload["fingerprint"]
            ):
                raise ReplacementDecisionError("Replacement decision identity or checksum mismatch")
            return decision
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ReplacementDecisionError("Stored replacement decision is invalid") from exc
