"""Asset-aware scanner for Canonical Asset Repository (CAR) v2.

The scanner discovers CAP asset directories, classifies each asset, reads any
existing manifest/profile metadata, and returns structured repository records.
It performs no writes and is therefore safe to use during dry runs, validation,
and migration planning.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

ASSET_DIRECTORY_PATTERN = re.compile(
    r"^(?P<asset_id>CAP-(?P<prefix>[A-Z]{3})-\d{3})(?:_(?P<slug>.+))?$"
)


class AssetClass(StrEnum):
    """High-level CAR asset classes."""

    VISUAL = "visual"
    CONFIGURATION = "configuration"
    BEHAVIOUR = "behaviour"
    UNKNOWN = "unknown"


VISUAL_CATEGORIES = frozenset(
    {
        "characters",
        "character",
        "ships",
        "ship",
        "locations",
        "location",
        "props",
        "prop",
        "planets",
        "planet",
        "technology",
        "technologies",
        "uniforms",
        "uniform",
        "vehicles",
        "vehicle",
        "environments",
        "environment",
        "effects",
        "effect",
    }
)

CONFIGURATION_CATEGORIES = frozenset(
    {
        "audio",
        "camera",
        "cameras",
        "lighting",
        "lights",
    }
)

BEHAVIOUR_CATEGORIES = frozenset(
    {
        "animation",
        "animations",
        "behaviour",
        "behaviours",
        "behavior",
        "behaviors",
        "motion",
        "motions",
        "lip_sync",
        "lip-sync",
        "lipsync",
    }
)

PREFIX_CLASS_MAP: Mapping[str, AssetClass] = {
    "AUD": AssetClass.CONFIGURATION,
    "CAM": AssetClass.CONFIGURATION,
    "LGT": AssetClass.CONFIGURATION,
    "CHR": AssetClass.VISUAL,
    "SHP": AssetClass.VISUAL,
    "LOC": AssetClass.VISUAL,
    "PRP": AssetClass.VISUAL,
    "PLN": AssetClass.VISUAL,
    "TEC": AssetClass.VISUAL,
    "UNI": AssetClass.VISUAL,
    "VEH": AssetClass.VISUAL,
    "ENV": AssetClass.VISUAL,
    "FX": AssetClass.VISUAL,
    "ANM": AssetClass.BEHAVIOUR,
    "MOT": AssetClass.BEHAVIOUR,
    "BEH": AssetClass.BEHAVIOUR,
    "LIP": AssetClass.BEHAVIOUR,
}


class CarScanError(RuntimeError):
    """Base exception for CAR repository scanning failures."""


class InvalidCarRootError(CarScanError):
    """Raised when a repository root cannot be scanned."""


@dataclass(frozen=True, slots=True)
class ScanIssue:
    """One non-fatal issue discovered while scanning an asset."""

    severity: str
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serialisable representation."""
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "path": self.path,
        }


@dataclass(slots=True)
class AssetRepositoryInfo:
    """Structured information about one asset repository directory."""

    asset_id: str
    name: str
    category: str
    asset_class: AssetClass
    path: Path
    relative_path: Path
    prefix: str
    repository_version: str
    manifest_path: Path | None = None
    profile_path: Path | None = None
    behaviour_path: Path | None = None
    manifest: dict[str, Any] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    folders: frozenset[str] = field(default_factory=frozenset)
    files: frozenset[str] = field(default_factory=frozenset)
    issues: list[ScanIssue] = field(default_factory=list)

    @property
    def has_manifest(self) -> bool:
        return self.manifest_path is not None and self.manifest_path.is_file()

    @property
    def has_profile(self) -> bool:
        return self.profile_path is not None and self.profile_path.is_file()

    @property
    def has_behaviour_definition(self) -> bool:
        return self.behaviour_path is not None and self.behaviour_path.is_file()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation."""
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "category": self.category,
            "asset_class": self.asset_class.value,
            "path": str(self.path),
            "relative_path": str(self.relative_path),
            "prefix": self.prefix,
            "repository_version": self.repository_version,
            "manifest_path": str(self.manifest_path) if self.manifest_path else None,
            "profile_path": str(self.profile_path) if self.profile_path else None,
            "behaviour_path": str(self.behaviour_path) if self.behaviour_path else None,
            "folders": sorted(self.folders),
            "files": sorted(self.files),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(slots=True)
class RepositoryScanResult:
    """Complete result of scanning a CAR repository."""

    root: Path
    assets: list[AssetRepositoryInfo] = field(default_factory=list)
    issues: list[ScanIssue] = field(default_factory=list)

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    def count_by_class(self) -> dict[str, int]:
        counts = {asset_class.value: 0 for asset_class in AssetClass}
        for asset in self.assets:
            counts[asset.asset_class.value] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "asset_count": self.asset_count,
            "asset_classes": self.count_by_class(),
            "issues": [issue.to_dict() for issue in self.issues],
            "assets": [asset.to_dict() for asset in self.assets],
        }


class CarRepositoryScanner:
    """Read-only scanner for a Canonical Asset Repository."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()

    def scan(self) -> RepositoryScanResult:
        """Scan the repository and return all recognised CAP assets."""
        self._validate_root()
        result = RepositoryScanResult(root=self.root)

        for asset_directory in self.iter_asset_directories():
            try:
                result.assets.append(self.scan_asset(asset_directory))
            except OSError as error:
                result.issues.append(
                    ScanIssue(
                        severity="error",
                        code="asset_scan_failed",
                        message=str(error),
                        path=str(asset_directory.relative_to(self.root)),
                    )
                )

        return result

    def iter_asset_directories(self) -> Iterator[Path]:
        """Yield recognised CAP asset directories in deterministic order."""
        self._validate_root()
        for category_directory in sorted(
            (path for path in self.root.iterdir() if path.is_dir()),
            key=lambda path: path.name.casefold(),
        ):
            for candidate in sorted(
                (path for path in category_directory.iterdir() if path.is_dir()),
                key=lambda path: path.name.casefold(),
            ):
                if ASSET_DIRECTORY_PATTERN.fullmatch(candidate.name):
                    yield candidate

    def scan_asset(self, asset_directory: Path | str) -> AssetRepositoryInfo:
        """Scan one asset directory.

        The directory must be located directly below a category directory under
        the configured repository root.
        """
        path = Path(asset_directory).expanduser().resolve()
        self._validate_asset_path(path)

        match = ASSET_DIRECTORY_PATTERN.fullmatch(path.name)
        if match is None:
            raise CarScanError(f"Invalid CAP asset directory name: {path.name}")

        category = path.parent.name
        prefix = match.group("prefix")
        asset_class = classify_asset(category=category, prefix=prefix)
        issues: list[ScanIssue] = []

        manifest_path = path / "manifest.json"
        profile_path = path / "profile.json"
        behaviour_path = self._first_existing(
            path / "behaviour.json",
            path / "behavior.json",
        )

        manifest = self._read_json(manifest_path, issues)
        profile = self._read_json(profile_path, issues)

        asset_id = _first_non_empty_string(
            manifest.get("asset_id"),
            profile.get("asset_id"),
            match.group("asset_id"),
        ).upper()

        name = _first_non_empty_string(
            manifest.get("name"),
            manifest.get("asset_name"),
            profile.get("name"),
            profile.get("asset_name"),
            _slug_to_name(match.group("slug")),
            asset_id,
        )

        entries = list(path.iterdir())
        folders = frozenset(entry.name for entry in entries if entry.is_dir())
        files = frozenset(entry.name for entry in entries if entry.is_file())
        repository_version = detect_repository_version(
            asset_directory=path,
            manifest=manifest,
            profile=profile,
            folders=folders,
        )

        declared_class = _declared_asset_class(manifest, profile)
        if declared_class is not None and declared_class != asset_class:
            issues.append(
                ScanIssue(
                    severity="warning",
                    code="asset_class_mismatch",
                    message=(
                        f"Declared asset class '{declared_class.value}' does not match "
                        f"detected class '{asset_class.value}'."
                    ),
                    path=str(path.relative_to(self.root)),
                )
            )

        if asset_class is AssetClass.UNKNOWN:
            issues.append(
                ScanIssue(
                    severity="warning",
                    code="unknown_asset_class",
                    message=(
                        f"Unable to classify category '{category}' with CAP prefix "
                        f"'{prefix}'."
                    ),
                    path=str(path.relative_to(self.root)),
                )
            )

        return AssetRepositoryInfo(
            asset_id=asset_id,
            name=name,
            category=category,
            asset_class=asset_class,
            path=path,
            relative_path=path.relative_to(self.root),
            prefix=prefix,
            repository_version=repository_version,
            manifest_path=manifest_path if manifest_path.is_file() else None,
            profile_path=profile_path if profile_path.is_file() else None,
            behaviour_path=behaviour_path,
            manifest=manifest,
            profile=profile,
            folders=folders,
            files=files,
            issues=issues,
        )

    def _validate_root(self) -> None:
        if not self.root.exists():
            raise InvalidCarRootError(f"CAR root does not exist: {self.root}")
        if not self.root.is_dir():
            raise InvalidCarRootError(f"CAR root is not a directory: {self.root}")

    def _validate_asset_path(self, path: Path) -> None:
        self._validate_root()
        if not path.exists():
            raise CarScanError(f"Asset directory does not exist: {path}")
        if not path.is_dir():
            raise CarScanError(f"Asset path is not a directory: {path}")
        try:
            relative = path.relative_to(self.root)
        except ValueError as error:
            raise CarScanError(
                f"Asset directory is outside CAR root: {path}"
            ) from error
        if len(relative.parts) != 2:
            raise CarScanError(
                "Asset directory must be directly below a category directory: "
                f"{relative}"
            )

    def _read_json(
        self,
        path: Path,
        issues: list[ScanIssue],
    ) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            issues.append(
                ScanIssue(
                    severity="warning",
                    code="json_unreadable",
                    message=str(error),
                    path=str(path.relative_to(self.root)),
                )
            )
            return {}
        except json.JSONDecodeError as error:
            issues.append(
                ScanIssue(
                    severity="warning",
                    code="json_invalid",
                    message=(
                        f"Invalid JSON at line {error.lineno}, column {error.colno}: "
                        f"{error.msg}"
                    ),
                    path=str(path.relative_to(self.root)),
                )
            )
            return {}

        if not isinstance(payload, dict):
            issues.append(
                ScanIssue(
                    severity="warning",
                    code="json_root_not_object",
                    message="JSON root must be an object.",
                    path=str(path.relative_to(self.root)),
                )
            )
            return {}
        return payload

    @staticmethod
    def _first_existing(*paths: Path) -> Path | None:
        return next((path for path in paths if path.is_file()), None)


def classify_asset(*, category: str, prefix: str = "") -> AssetClass:
    """Classify an asset using category first and CAP prefix as fallback."""
    normalised = _normalise_category(category)
    if normalised in VISUAL_CATEGORIES:
        return AssetClass.VISUAL
    if normalised in CONFIGURATION_CATEGORIES:
        return AssetClass.CONFIGURATION
    if normalised in BEHAVIOUR_CATEGORIES:
        return AssetClass.BEHAVIOUR
    return PREFIX_CLASS_MAP.get(prefix.upper(), AssetClass.UNKNOWN)


def detect_repository_version(
    *,
    asset_directory: Path,
    manifest: Mapping[str, Any] | None = None,
    profile: Mapping[str, Any] | None = None,
    folders: Iterable[str] | None = None,
) -> str:
    """Detect the most likely CAR repository version for one asset."""
    manifest = manifest or {}
    profile = profile or {}

    declared = _first_non_empty_string(
        manifest.get("repository_version"),
        profile.get("repository_version"),
        _nested_value(manifest, "car", "repository_version"),
        _nested_value(profile, "car", "repository_version"),
    )
    if declared:
        return declared

    folder_names = set(folders or ())
    if not folder_names:
        folder_names = {
            child.name for child in asset_directory.iterdir() if child.is_dir()
        }

    if "canon" in folder_names or "metadata" in folder_names:
        return "2.0"
    if "approved" in folder_names or "references" in folder_names:
        return "1.0"
    return "legacy"


def _declared_asset_class(
    manifest: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> AssetClass | None:
    value = _first_non_empty_string(
        manifest.get("asset_class"),
        profile.get("asset_class"),
    ).casefold()
    if not value:
        return None
    try:
        return AssetClass(value)
    except ValueError:
        return AssetClass.UNKNOWN


def _normalise_category(category: str) -> str:
    return category.strip().casefold().replace(" ", "_")


def _slug_to_name(slug: str | None) -> str:
    if not slug:
        return ""
    return " ".join(part for part in slug.replace("-", "_").split("_") if part)


def _first_non_empty_string(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _nested_value(payload: Mapping[str, Any], *keys: str) -> object:
    current: object = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


__all__ = [
    "ASSET_DIRECTORY_PATTERN",
    "AssetClass",
    "AssetRepositoryInfo",
    "BEHAVIOUR_CATEGORIES",
    "CONFIGURATION_CATEGORIES",
    "CarRepositoryScanner",
    "CarScanError",
    "InvalidCarRootError",
    "PREFIX_CLASS_MAP",
    "RepositoryScanResult",
    "ScanIssue",
    "VISUAL_CATEGORIES",
    "classify_asset",
    "detect_repository_version",
]
