"""Deterministic asset staging for production render jobs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class StagedAssetKind(StrEnum):
    """Production dependency categories supported by the staging service."""

    WORKFLOW = "workflow"
    MODEL = "model"
    LORA = "lora"
    REFERENCE = "reference"
    AUDIO = "audio"
    CONFIGURATION = "configuration"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class StagingRequest:
    """One source dependency requested for a production job."""

    asset_id: str
    kind: StagedAssetKind
    source_path: Path
    target_name: str | None = None
    expected_checksum: str | None = None
    required: bool = True
    metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id must not be empty")
        if self.target_name is not None and Path(self.target_name).name != self.target_name:
            raise ValueError("target_name must be a file name without directories")


@dataclass(frozen=True, slots=True)
class StagingPlanItem:
    """Resolved source and destination for one staging request."""

    request: StagingRequest
    destination_path: Path


@dataclass(frozen=True, slots=True)
class StagingPlan:
    """Deterministic staging plan for one render job."""

    job_id: str
    staging_directory: Path
    items: tuple[StagingPlanItem, ...]


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    """One verified artifact available in a production staging directory."""

    asset_id: str
    kind: StagedAssetKind
    source_path: Path
    staged_path: Path
    checksum: str
    size_bytes: int
    cache_reused: bool
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class StagingManifest:
    """Immutable record of all dependencies staged for one render job."""

    job_id: str
    staging_directory: Path
    artifacts: tuple[StagedArtifact, ...]
    checksum: str
    schema_version: str = "1.0"
    metadata: dict[str, str] = field(default_factory=dict)

    def artifact(self, asset_id: str) -> StagedArtifact | None:
        """Return one staged artifact by stable identity."""
        return next((item for item in self.artifacts if item.asset_id == asset_id), None)


@dataclass(frozen=True, slots=True)
class AssetStagingConfig:
    """File-system policy for production dependency staging."""

    staging_root: Path
    cache_root: Path | None = None
    use_hardlinks: bool = False
    verify_after_copy: bool = True

    @property
    def effective_cache_root(self) -> Path:
        """Return the configured or default content-addressed cache root."""
        return self.cache_root or self.staging_root / ".cache"


class AssetStagingError(RuntimeError):
    """Raised when production dependencies cannot be staged safely."""


class AssetStager:
    """Plan, verify, cache, stage, serialize, and clean production assets."""

    def __init__(self, config: AssetStagingConfig) -> None:
        self.config = config

    def plan(
        self,
        job_id: str,
        requests: tuple[StagingRequest, ...],
    ) -> StagingPlan:
        """Build a collision-safe deterministic staging plan."""
        if not job_id.strip():
            raise AssetStagingError("job_id must not be empty")
        staging_directory = self.config.staging_root / self._safe_segment(job_id)
        items: list[StagingPlanItem] = []
        destinations: dict[Path, Path] = {}
        asset_ids: set[str] = set()
        for request in requests:
            if request.asset_id in asset_ids:
                raise AssetStagingError(f"Duplicate staging asset ID: {request.asset_id}")
            asset_ids.add(request.asset_id)
            filename = request.target_name or request.source_path.name
            if not filename:
                raise AssetStagingError(
                    f"Unable to determine target file name for {request.asset_id}"
                )
            destination = staging_directory / request.kind.value / filename
            previous_source = destinations.get(destination)
            if previous_source is not None and previous_source != request.source_path:
                raise AssetStagingError(f"Staging target collision: {destination}")
            destinations[destination] = request.source_path
            items.append(StagingPlanItem(request, destination))
        items.sort(key=lambda item: (item.request.kind.value, item.request.asset_id))
        return StagingPlan(job_id, staging_directory, tuple(items))

    def stage(self, plan: StagingPlan) -> StagingManifest:
        """Verify and stage every dependency in a plan."""
        artifacts: list[StagedArtifact] = []
        try:
            for item in plan.items:
                artifact = self._stage_item(item)
                if artifact is not None:
                    artifacts.append(artifact)
        except (OSError, ValueError) as exc:
            raise AssetStagingError(f"Unable to stage assets for {plan.job_id}: {exc}") from exc
        checksum = self.manifest_checksum(plan.job_id, tuple(artifacts), "1.0")
        return StagingManifest(
            job_id=plan.job_id,
            staging_directory=plan.staging_directory,
            artifacts=tuple(artifacts),
            checksum=checksum,
        )

    def validate(self, manifest: StagingManifest) -> None:
        """Validate staged files and manifest integrity."""
        expected_manifest = self.manifest_checksum(
            manifest.job_id,
            manifest.artifacts,
            manifest.schema_version,
        )
        if manifest.checksum != expected_manifest:
            raise AssetStagingError("Staging manifest checksum mismatch")
        for artifact in manifest.artifacts:
            if not artifact.staged_path.is_file():
                raise AssetStagingError(
                    f"Staged artifact is missing: {artifact.staged_path}"
                )
            if self.file_checksum(artifact.staged_path) != artifact.checksum:
                raise AssetStagingError(
                    f"Staged artifact checksum mismatch: {artifact.asset_id}"
                )

    def cleanup(self, manifest: StagingManifest) -> None:
        """Remove one job staging directory without deleting shared cache data."""
        root = self.config.staging_root.resolve(strict=False)
        target = manifest.staging_directory.resolve(strict=False)
        if target == root or root not in target.parents:
            raise AssetStagingError(f"Refusing unsafe staging cleanup: {target}")
        shutil.rmtree(target, ignore_errors=False)

    @staticmethod
    def dumps(manifest: StagingManifest) -> str:
        """Serialize a staging manifest to stable JSON."""
        return json.dumps(
            AssetStager.to_dict(manifest),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ) + "\n"

    @staticmethod
    def loads(payload: str) -> StagingManifest:
        """Restore a staging manifest from JSON."""
        try:
            raw = json.loads(payload)
            if not isinstance(raw, dict):
                raise TypeError("Manifest root must be an object")
            return AssetStager.from_dict(raw)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise AssetStagingError(f"Invalid staging manifest: {exc}") from exc

    @staticmethod
    def to_dict(manifest: StagingManifest) -> dict[str, Any]:
        """Convert a staging manifest into JSON-compatible data."""
        return {
            "schema_version": manifest.schema_version,
            "job_id": manifest.job_id,
            "staging_directory": str(manifest.staging_directory),
            "artifacts": [
                {
                    "asset_id": item.asset_id,
                    "kind": item.kind.value,
                    "source_path": str(item.source_path),
                    "staged_path": str(item.staged_path),
                    "checksum": item.checksum,
                    "size_bytes": item.size_bytes,
                    "cache_reused": item.cache_reused,
                    "metadata": [list(value) for value in item.metadata],
                }
                for item in manifest.artifacts
            ],
            "checksum": manifest.checksum,
            "metadata": dict(manifest.metadata),
        }

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> StagingManifest:
        """Restore a staging manifest from JSON-compatible data."""
        return StagingManifest(
            job_id=str(raw["job_id"]),
            staging_directory=Path(str(raw["staging_directory"])),
            artifacts=tuple(
                StagedArtifact(
                    asset_id=str(item["asset_id"]),
                    kind=StagedAssetKind(str(item["kind"])),
                    source_path=Path(str(item["source_path"])),
                    staged_path=Path(str(item["staged_path"])),
                    checksum=str(item["checksum"]),
                    size_bytes=int(item["size_bytes"]),
                    cache_reused=bool(item["cache_reused"]),
                    metadata=tuple(
                        (str(value[0]), str(value[1]))
                        for value in item.get("metadata", [])
                    ),
                )
                for item in raw.get("artifacts", [])
            ),
            checksum=str(raw["checksum"]),
            schema_version=str(raw.get("schema_version", "1.0")),
            metadata={
                str(key): str(value) for key, value in raw.get("metadata", {}).items()
            },
        )

    def _stage_item(self, item: StagingPlanItem) -> StagedArtifact | None:
        request = item.request
        source = request.source_path.expanduser().resolve(strict=False)
        if not source.is_file():
            if request.required:
                raise AssetStagingError(f"Required staging source not found: {source}")
            return None
        checksum = self.file_checksum(source)
        if request.expected_checksum is not None:
            expected = request.expected_checksum.lower()
            if checksum != expected:
                raise AssetStagingError(
                    f"Source checksum mismatch for {request.asset_id}: "
                    f"expected {expected}, found {checksum}"
                )
        cache_path = self.config.effective_cache_root / checksum[:2] / checksum
        cache_reused = cache_path.is_file() and self.file_checksum(cache_path) == checksum
        if not cache_reused:
            self._atomic_copy(source, cache_path)
        self._materialize(cache_path, item.destination_path)
        if self.config.verify_after_copy:
            staged_checksum = self.file_checksum(item.destination_path)
            if staged_checksum != checksum:
                raise AssetStagingError(
                    f"Staged checksum mismatch for {request.asset_id}"
                )
        return StagedArtifact(
            asset_id=request.asset_id,
            kind=request.kind,
            source_path=source,
            staged_path=item.destination_path,
            checksum=checksum,
            size_bytes=item.destination_path.stat().st_size,
            cache_reused=cache_reused,
            metadata=request.metadata,
        )

    def _materialize(self, cache_path: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and self.file_checksum(destination) == self.file_checksum(
            cache_path
        ):
            return
        destination.unlink(missing_ok=True)
        if self.config.use_hardlinks:
            try:
                os.link(cache_path, destination)
                return
            except OSError:
                pass
        self._atomic_copy(cache_path, destination)

    @staticmethod
    def _atomic_copy(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        shutil.copy2(source, temporary)
        temporary.replace(destination)

    @staticmethod
    def file_checksum(path: Path) -> str:
        """Return the SHA-256 checksum of one file."""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def manifest_checksum(
        job_id: str,
        artifacts: tuple[StagedArtifact, ...],
        schema_version: str,
    ) -> str:
        """Return a deterministic checksum for one staging manifest."""
        payload = {
            "schema_version": schema_version,
            "job_id": job_id,
            "artifacts": [
                {
                    "asset_id": item.asset_id,
                    "kind": item.kind.value,
                    "checksum": item.checksum,
                    "size_bytes": item.size_bytes,
                    "metadata": [list(value) for value in item.metadata],
                }
                for item in artifacts
            ],
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _safe_segment(value: str) -> str:
        safe = "".join(
            character
            if character.isalnum() or character in "-_."
            else "_"
            for character in value.strip()
        )
        if safe in {"", ".", ".."}:
            raise AssetStagingError(f"Unsafe staging path segment: {value!r}")
        return safe
