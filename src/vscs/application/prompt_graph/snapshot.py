"""Immutable prompt graph snapshots and deterministic checksums."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from .models import PromptGraph


@dataclass(frozen=True, slots=True)
class PromptGraphSnapshot:
    """Versioned immutable capture of one prompt graph."""

    snapshot_id: str
    graph: PromptGraph
    created_at: datetime
    checksum: str

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip():
            raise ValueError("snapshot_id is required")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.checksum != graph_checksum(self.graph):
            raise ValueError("snapshot checksum does not match graph content")

    @classmethod
    def capture(
        cls,
        graph: PromptGraph,
        *,
        snapshot_id: str,
        created_at: datetime | None = None,
    ) -> PromptGraphSnapshot:
        """Capture a graph using canonical serialized content."""
        return cls(
            snapshot_id=snapshot_id,
            graph=graph,
            created_at=created_at or datetime.now(UTC),
            checksum=graph_checksum(graph),
        )


def graph_checksum(graph: PromptGraph) -> str:
    """Return a stable SHA-256 checksum for graph content."""
    payload = json.dumps(
        graph.to_dict(),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
