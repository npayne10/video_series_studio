"""Adapters exposing current VSCS resources to the ACPP resolver."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vscs.application.caps import (
    CanonicalReferenceError,
    CanonicalReferenceService,
    CAPError,
    CAPService,
)
from vscs.application.car.validator.prompt_discovery import PromptPackageDiscoverer
from vscs.domain.caps import CanonicalReferenceStatus, CAPStatus

from .resolution import (
    AssetResolutionRecord,
    BehaviourResolutionRecord,
    CanonicalReferenceResolution,
)


class CAPAssetResolutionCatalog:
    """Resolve assets through current CAP and canonical-reference services."""

    def __init__(
        self,
        caps: CAPService,
        references: CanonicalReferenceService,
    ) -> None:
        self.caps = caps
        self.references = references

    def resolve_asset(self, asset_id: str) -> AssetResolutionRecord | None:
        """Return CAP and approved canonical-reference state for one asset."""
        try:
            cap = self.caps.get(asset_id)
            references = self.references.list_for_cap(
                asset_id,
                status=CanonicalReferenceStatus.APPROVED,
            )
        except (CAPError, CanonicalReferenceError):
            return None

        project_directory = self.caps.assets.projects.project_directory
        resolved_references = tuple(
            CanonicalReferenceResolution(
                reference_id=str(reference.id),
                path=str(reference.file_path),
                role=reference.role.value,
                reference_type=reference.reference_type.value,
                approved=reference.status is CanonicalReferenceStatus.APPROVED,
                locked=reference.locked,
                checksum=self._reference_checksum(
                    project_directory,
                    reference.file_path,
                ),
            )
            for reference in references
        )
        return AssetResolutionRecord(
            asset_id=cap.asset_id,
            cap_id=f"CAP:{cap.id}",
            cap_version=cap.version,
            cap_approved=cap.status is CAPStatus.APPROVED,
            canonical_references=resolved_references,
            checksum=self._cap_checksum(cap.model_dump(mode="json")),
        )

    @staticmethod
    def _reference_checksum(
        project_directory: Path | None,
        reference_path: Path,
    ) -> str | None:
        if project_directory is None:
            return None
        path = (
            reference_path
            if reference_path.is_absolute()
            else project_directory / reference_path
        )
        if not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _cap_checksum(payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class FilesystemBehaviourResolutionCatalog:
    """Resolve behaviour assets and their discovered prompt packages."""

    MANIFEST_NAMES = ("behaviour.json", "behavior.json")

    def __init__(
        self,
        root: Path,
        discoverer: PromptPackageDiscoverer | None = None,
    ) -> None:
        self.root = root
        self.discoverer = discoverer or PromptPackageDiscoverer()

    def resolve_behaviour(self, package_id: str) -> BehaviourResolutionRecord | None:
        """Resolve one behaviour package beneath the configured root."""
        package_path = self._find_package(package_id)
        if package_path is None:
            return None
        manifest_path = next(
            (
                package_path / name
                for name in self.MANIFEST_NAMES
                if (package_path / name).is_file()
            ),
            None,
        )
        if manifest_path is None:
            return BehaviourResolutionRecord(
                package_id=package_id,
                version="unknown",
                structurally_valid=False,
                manifest_path=str(package_path),
            )

        manifest = self._load_manifest(manifest_path)
        prompts = self.discoverer.discover(package_path / "prompts")
        return BehaviourResolutionRecord(
            package_id=str(
                manifest.get("asset_id") or manifest.get("id") or package_id
            ),
            version=str(manifest.get("version") or "1.0"),
            structurally_valid=(
                bool(manifest)
                and prompts.package_count > 0
                and prompts.valid_package_count == prompts.package_count
            ),
            manifest_path=str(manifest_path),
            prompt_package_ids=tuple(
                package.name for package in prompts.packages
            ),
            dependency_ids=self._dependency_ids(manifest),
            checksum=self._file_checksum(manifest_path),
        )

    def _find_package(self, package_id: str) -> Path | None:
        direct = self.root / package_id
        if direct.is_dir():
            return direct
        if not self.root.is_dir():
            return None
        target = package_id.casefold()
        return next(
            (
                entry
                for entry in sorted(
                    self.root.iterdir(),
                    key=lambda path: path.name.casefold(),
                )
                if entry.is_dir() and entry.name.casefold() == target
            ),
            None,
        )

    @staticmethod
    def _load_manifest(path: Path) -> dict[str, Any]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    @staticmethod
    def _dependency_ids(manifest: dict[str, Any]) -> tuple[str, ...]:
        values = manifest.get("dependencies", ())
        if isinstance(values, dict):
            values = values.get("assets", ())
        if not isinstance(values, list | tuple):
            return ()
        dependencies: list[str] = []
        for value in values:
            if isinstance(value, str) and value.strip():
                dependencies.append(value.strip())
            elif isinstance(value, dict):
                candidate = value.get("asset_id") or value.get("id")
                if isinstance(candidate, str) and candidate.strip():
                    dependencies.append(candidate.strip())
        return tuple(dict.fromkeys(dependencies))

    @staticmethod
    def _file_checksum(path: Path) -> str | None:
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            return None
