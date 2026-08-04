"""Checksum-based incremental prompt compilation history and invalidation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .models import PromptGraph
from .renderer_profiles import ProfiledPromptPackage, RendererPromptProfile
from .snapshot import graph_checksum


class CompilationDependencyKind(StrEnum):
    """Dependency categories capable of invalidating compiled prompts."""

    CANONICAL_ASSET = "canonical_asset"
    REFERENCE_IMAGE = "reference_image"
    CONTINUITY = "continuity"
    VOICE = "voice"
    LIGHTING_PROFILE = "lighting_profile"
    CAMERA_PROFILE = "camera_profile"
    RENDERER_PROFILE = "renderer_profile"
    WORKFLOW_MANIFEST = "workflow_manifest"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class CompilationDependency:
    """One versioned dependency included in an incremental fingerprint."""

    kind: CompilationDependencyKind
    dependency_id: str
    checksum: str

    def __post_init__(self) -> None:
        if not self.dependency_id.strip() or not self.checksum.strip():
            raise ValueError("dependency_id and checksum are required")


@dataclass(frozen=True, slots=True)
class CompilationFingerprint:
    """Reproducible identity for one compiled graph/profile/dependency set."""

    graph_checksum: str
    renderer_profile_id: str
    renderer_profile_checksum: str
    dependencies: tuple[CompilationDependency, ...]
    combined_checksum: str


@dataclass(frozen=True, slots=True)
class CompiledPromptRecord:
    """Latest successful compiled package retained for one batch item."""

    item_id: str
    shot_id: str
    fingerprint: CompilationFingerprint
    package: ProfiledPromptPackage
    compiled_at: datetime


@dataclass(slots=True)
class IncrementalCompilationHistory:
    """In-memory compiled prompt history and explicit invalidation state."""

    _records: dict[str, CompiledPromptRecord] = field(default_factory=dict)
    _invalidated_items: set[str] = field(default_factory=set)

    def get(self, item_id: str) -> CompiledPromptRecord | None:
        return self._records.get(item_id)

    def register(self, record: CompiledPromptRecord) -> CompiledPromptRecord:
        self._records[record.item_id] = record
        self._invalidated_items.discard(record.item_id)
        return record

    def all(self) -> tuple[CompiledPromptRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))

    def invalidate_item(self, item_id: str) -> bool:
        if item_id not in self._records:
            return False
        self._invalidated_items.add(item_id)
        return True

    def invalidate_dependency(
        self,
        kind: CompilationDependencyKind,
        dependency_id: str,
    ) -> tuple[str, ...]:
        affected = tuple(
            sorted(
                record.item_id
                for record in self._records.values()
                if any(
                    dependency.kind is kind
                    and dependency.dependency_id == dependency_id
                    for dependency in record.fingerprint.dependencies
                )
            )
        )
        self._invalidated_items.update(affected)
        return affected

    def is_invalidated(self, item_id: str) -> bool:
        return item_id in self._invalidated_items

    def clear(self) -> None:
        self._records.clear()
        self._invalidated_items.clear()


@dataclass(slots=True)
class IncrementalCompilationService:
    """Create fingerprints and decide whether a prompt item must rebuild."""

    history: IncrementalCompilationHistory

    def fingerprint(
        self,
        graph: PromptGraph,
        profile: RendererPromptProfile,
        dependencies: tuple[CompilationDependency, ...] = (),
    ) -> CompilationFingerprint:
        ordered_dependencies = tuple(
            sorted(
                dependencies,
                key=lambda item: (item.kind.value, item.dependency_id, item.checksum),
            )
        )
        profile_checksum = self._profile_checksum(profile)
        graph_digest = graph_checksum(graph)
        payload = {
            "graph_checksum": graph_digest,
            "renderer_profile_id": profile.profile_id,
            "renderer_profile_checksum": profile_checksum,
            "dependencies": [
                {
                    "kind": item.kind.value,
                    "dependency_id": item.dependency_id,
                    "checksum": item.checksum,
                }
                for item in ordered_dependencies
            ],
        }
        combined = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        return CompilationFingerprint(
            graph_checksum=graph_digest,
            renderer_profile_id=profile.profile_id,
            renderer_profile_checksum=profile_checksum,
            dependencies=ordered_dependencies,
            combined_checksum=combined,
        )

    def reusable(
        self,
        item_id: str,
        fingerprint: CompilationFingerprint,
        *,
        force_recompile: bool = False,
    ) -> CompiledPromptRecord | None:
        if force_recompile or self.history.is_invalidated(item_id):
            return None
        record = self.history.get(item_id)
        if record is None:
            return None
        if record.fingerprint.combined_checksum != fingerprint.combined_checksum:
            return None
        return record

    def record(
        self,
        item_id: str,
        shot_id: str,
        fingerprint: CompilationFingerprint,
        package: ProfiledPromptPackage,
    ) -> CompiledPromptRecord:
        return self.history.register(
            CompiledPromptRecord(
                item_id=item_id,
                shot_id=shot_id,
                fingerprint=fingerprint,
                package=package,
                compiled_at=datetime.now(UTC),
            )
        )

    @staticmethod
    def _profile_checksum(profile: RendererPromptProfile) -> str:
        payload = asdict(profile)
        payload["renderer"] = profile.renderer.value
        payload["quality_level"] = profile.quality_level.value
        payload["section_order"] = [kind.value for kind in profile.section_order]
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
