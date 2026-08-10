"""Validation models and stable diagnostic codes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..scanner import AssetClass

if TYPE_CHECKING:
    from .prompt_discovery import PromptPackage


class ValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ValidationCode(StrEnum):
    UNKNOWN = "UNKNOWN"
    DUPLICATE_ASSET_ID = "DUPLICATE_ASSET_ID"
    INVALID_JSON = "INVALID_JSON"
    INVALID_MANIFEST = "INVALID_MANIFEST"
    INVALID_PROFILE = "INVALID_PROFILE"
    INVALID_BEHAVIOUR = "INVALID_BEHAVIOUR"
    MISSING_DIRECTORY = "MISSING_DIRECTORY"
    MISSING_FILE = "MISSING_FILE"
    MISSING_CANONICAL_IMAGE = "MISSING_CANONICAL_IMAGE"
    MISSING_METADATA = "MISSING_METADATA"
    INVALID_SCHEMA = "INVALID_SCHEMA"
    UNKNOWN_ASSET_CLASS = "UNKNOWN_ASSET_CLASS"
    INVALID_REPOSITORY = "INVALID_REPOSITORY"
    EMPTY_DIRECTORY = "EMPTY_DIRECTORY"
    DUPLICATE_HASH = "DUPLICATE_HASH"
    UNUSED_FILE = "UNUSED_FILE"
    PROMPT_PACKAGE_DISCOVERED = "PROMPT_PACKAGE_DISCOVERED"
    MULTIPLE_MANIFESTS = "MULTIPLE_MANIFESTS"
    UNEXPECTED_DIRECTORY = "UNEXPECTED_DIRECTORY"


@dataclass(slots=True)
class ValidationDiagnostic:
    severity: ValidationSeverity
    code: ValidationCode
    asset_id: str | None
    path: Path | None
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AssetValidationResult:
    asset_id: str
    asset_class: AssetClass
    asset_path: Path
    passed: bool = True
    diagnostics: list[ValidationDiagnostic] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)
    image_count: int = 0
    metadata_count: int = 0
    prompt_count: int = 0
    prompt_packages: list[PromptPackage] = field(default_factory=list)
    prompt_packages_valid: int = 0
    prompt_packages_ignored: int = 0


@dataclass(slots=True)
class RepositoryValidationResult:
    repository: Path | None
    passed: bool = True
    diagnostics: list[ValidationDiagnostic] = field(default_factory=list)
    assets: list[AssetValidationResult] = field(default_factory=list)
    duplicate_asset_ids: set[str] = field(default_factory=set)
    duplicate_hashes: dict[str, list[str]] = field(default_factory=dict)
    repository_health: float = 100.0
    total_assets: int = 0
    passed_assets: int = 0
    failed_assets: int = 0
    warnings: int = 0
    errors: int = 0
    critical: int = 0
