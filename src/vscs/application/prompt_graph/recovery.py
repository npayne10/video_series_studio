"""Persistent checkpointing and deterministic recovery for batch compilation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vscs.application.rendering import QualityLevel, RendererKind

from .batch import (
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
)
from .context import PromptGraphBuildContext
from .incremental import CompilationDependency, CompilationDependencyKind
from .validation import PromptGraphResourceInventory


@dataclass(frozen=True, slots=True)
class BatchRecoveryCheckpoint:
    """Durable execution state for one batch request."""

    request: BatchCompilationRequest
    item_statuses: tuple[tuple[str, BatchCompilationItemStatus], ...] = ()
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.updated_at.tzinfo is None:
            raise ValueError("updated_at must be timezone-aware")
        known = {item.item_id for item in self.request.items}
        identities = tuple(item_id for item_id, _status in self.item_statuses)
        if len(identities) != len(set(identities)):
            raise ValueError("checkpoint item statuses must be unique")
        if not set(identities).issubset(known):
            raise ValueError("checkpoint references an unknown batch item")

    def status_for(self, item_id: str) -> BatchCompilationItemStatus:
        return dict(self.item_statuses).get(item_id, BatchCompilationItemStatus.PENDING)

    @property
    def complete(self) -> bool:
        terminal = {
            BatchCompilationItemStatus.COMPLETED,
            BatchCompilationItemStatus.SKIPPED,
        }
        return all(
            self.status_for(item.item_id) in terminal
            for item in self.request.items
        )


@dataclass(slots=True)
class BatchRecoveryStore:
    """Persist recovery checkpoints in one deterministic JSON document."""

    path: Path

    def save(self, checkpoint: BatchRecoveryCheckpoint) -> None:
        checkpoints = {item.request.batch_id: item for item in self.load_all()}
        checkpoints[checkpoint.request.batch_id] = checkpoint
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "checkpoints": [
                _checkpoint_to_dict(checkpoints[key]) for key in sorted(checkpoints)
            ],
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def remove(self, batch_id: str) -> None:
        checkpoints = {
            item.request.batch_id: item
            for item in self.load_all()
            if item.request.batch_id != batch_id
        }
        if not checkpoints:
            self.path.unlink(missing_ok=True)
            return
        payload = {
            "version": 1,
            "checkpoints": [
                _checkpoint_to_dict(checkpoints[key]) for key in sorted(checkpoints)
            ],
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def load_all(self) -> tuple[BatchRecoveryCheckpoint, ...]:
        if not self.path.exists():
            return ()
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("version") != 1:
            raise ValueError("unsupported batch recovery document version")
        checkpoints = raw.get("checkpoints", [])
        if not isinstance(checkpoints, list):
            raise ValueError("recovery checkpoints must be an array")
        return tuple(_checkpoint_from_dict(item) for item in checkpoints)


@dataclass(slots=True)
class BatchRecoveryService:
    """Checkpoint item outcomes and construct safe resumable requests."""

    store: BatchRecoveryStore
    _checkpoints: dict[str, BatchRecoveryCheckpoint] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._checkpoints = {
            checkpoint.request.batch_id: checkpoint
            for checkpoint in self.store.load_all()
        }

    def begin(self, request: BatchCompilationRequest) -> BatchRecoveryCheckpoint:
        checkpoint = self._checkpoints.get(request.batch_id)
        if checkpoint is None:
            checkpoint = BatchRecoveryCheckpoint(request)
        elif checkpoint.request != request:
            raise ValueError(f"Recovery request changed for batch: {request.batch_id}")
        self._persist(checkpoint)
        return checkpoint

    def record_result(
        self,
        batch_id: str,
        result: BatchCompilationItemResult,
    ) -> BatchRecoveryCheckpoint:
        checkpoint = self.require(batch_id)
        statuses = dict(checkpoint.item_statuses)
        statuses[result.item_id] = result.status
        updated = replace(
            checkpoint,
            item_statuses=tuple(sorted(statuses.items())),
            updated_at=datetime.now(UTC),
        )
        self._persist(updated)
        return updated

    def require(self, batch_id: str) -> BatchRecoveryCheckpoint:
        try:
            return self._checkpoints[batch_id]
        except KeyError as exc:
            raise KeyError(f"No recovery checkpoint for batch: {batch_id}") from exc

    def resumable_request(
        self,
        batch_id: str,
        *,
        retry_failed: bool = True,
        new_batch_id: str | None = None,
    ) -> BatchCompilationRequest | None:
        checkpoint = self.require(batch_id)
        reusable = {
            BatchCompilationItemStatus.COMPLETED,
            BatchCompilationItemStatus.SKIPPED,
        }
        if not retry_failed:
            reusable.add(BatchCompilationItemStatus.FAILED)
        items = tuple(
            item
            for item in checkpoint.request.ordered_items
            if checkpoint.status_for(item.item_id) not in reusable
        )
        if not items:
            return None
        return BatchCompilationRequest.create(
            new_batch_id or checkpoint.request.batch_id,
            items,
        )

    def pending_checkpoints(self) -> tuple[BatchRecoveryCheckpoint, ...]:
        return tuple(
            self._checkpoints[key]
            for key in sorted(self._checkpoints)
            if not self._checkpoints[key].complete
        )

    def clear(self, batch_id: str) -> None:
        self._checkpoints.pop(batch_id, None)
        self.store.remove(batch_id)

    def _persist(self, checkpoint: BatchRecoveryCheckpoint) -> None:
        self._checkpoints[checkpoint.request.batch_id] = checkpoint
        self.store.save(checkpoint)


def _checkpoint_to_dict(checkpoint: BatchRecoveryCheckpoint) -> dict[str, Any]:
    return {
        "request": _request_to_dict(checkpoint.request),
        "item_statuses": [
            [item_id, status.value] for item_id, status in checkpoint.item_statuses
        ],
        "updated_at": checkpoint.updated_at.isoformat(),
    }


def _checkpoint_from_dict(raw: dict[str, Any]) -> BatchRecoveryCheckpoint:
    return BatchRecoveryCheckpoint(
        request=_request_from_dict(raw["request"]),
        item_statuses=tuple(
            (str(item_id), BatchCompilationItemStatus(str(status)))
            for item_id, status in raw.get("item_statuses", [])
        ),
        updated_at=datetime.fromisoformat(str(raw["updated_at"])),
    )


def _request_to_dict(request: BatchCompilationRequest) -> dict[str, Any]:
    return {
        "batch_id": request.batch_id,
        "created_at": request.created_at.isoformat(),
        "items": [_item_to_dict(item) for item in request.items],
    }


def _request_from_dict(raw: dict[str, Any]) -> BatchCompilationRequest:
    return BatchCompilationRequest(
        batch_id=str(raw["batch_id"]),
        items=tuple(_item_from_dict(item) for item in raw["items"]),
        created_at=datetime.fromisoformat(str(raw["created_at"])),
    )


def _item_to_dict(item: BatchCompilationItem) -> dict[str, Any]:
    context = asdict(item.context)
    context["renderer"] = item.context.renderer.value
    context["quality_level"] = item.context.quality_level.value
    return {
        "item_id": item.item_id,
        "context": context,
        "inventory": item.inventory.to_dict(),
        "sequence": item.sequence,
        "renderer_profile_id": item.renderer_profile_id,
        "require_production_ready": item.require_production_ready,
        "dependencies": [
            {
                "kind": dependency.kind.value,
                "dependency_id": dependency.dependency_id,
                "checksum": dependency.checksum,
            }
            for dependency in item.dependencies
        ],
        "force_recompile": item.force_recompile,
    }


def _item_from_dict(raw: dict[str, Any]) -> BatchCompilationItem:
    context_raw = dict(raw["context"])
    context_raw["renderer"] = RendererKind(context_raw["renderer"])
    context_raw["quality_level"] = QualityLevel(context_raw["quality_level"])
    return BatchCompilationItem(
        item_id=str(raw["item_id"]),
        context=PromptGraphBuildContext(**context_raw),
        inventory=PromptGraphResourceInventory.from_dict(raw.get("inventory")),
        sequence=int(raw.get("sequence", 0)),
        renderer_profile_id=raw.get("renderer_profile_id"),
        require_production_ready=bool(raw.get("require_production_ready", True)),
        dependencies=tuple(
            CompilationDependency(
                CompilationDependencyKind(item["kind"]),
                str(item["dependency_id"]),
                str(item["checksum"]),
            )
            for item in raw.get("dependencies", [])
        ),
        force_recompile=bool(raw.get("force_recompile", False)),
    )
