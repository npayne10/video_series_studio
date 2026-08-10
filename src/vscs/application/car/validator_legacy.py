# =============================================================================
# VSCS - Video Series Creation System
#
# File: validator.py
#
# Phase: 12.1.1
# Component: CAR Repository Verifier
#
# Copyright (c) 2026 S.S. Drake / VSCS Project
#
# Description:
#     Read-only verification engine for Canonical Asset Repositories.
#     Validates repository integrity, asset completeness, metadata,
#     canonical images, manifests and repository health.
# =============================================================================


"""
VSCS Canonical Asset Repository (CAR) Validator

File:
    validator.py

Description:
    Production-quality validation engine for Canonical Asset Repositories.

Responsibilities
----------------
* Validate repository structure
* Validate every asset
* Validate manifests and metadata
* Detect missing required files
* Detect duplicate IDs
* Produce repository diagnostics
* Produce repository health score

The validator NEVER modifies repository contents.
It is a read-only quality assurance subsystem.

Author:
    VSCS Development Team
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .scanner import (
    AssetClass,
    AssetRepositoryInfo,
    AssetRepositoryScanner,
    RepositoryScanResult,
)

LOGGER = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

REPOSITORY_VERSION = "2.0"

DEFAULT_MANIFEST = "manifest.json"

DEFAULT_CAP = "cap.json"

DEFAULT_PROFILE = "profile.json"

DEFAULT_BEHAVIOUR = "behaviour.json"

DEFAULT_DESCRIPTION = "description.md"

CANON_FOLDER = "canon"

PROMPTS_FOLDER = "prompts"

METADATA_FOLDER = "metadata"

THUMBNAILS_FOLDER = "thumbnails"

CANDIDATES_FOLDER = "candidates"

REJECTED_FOLDER = "rejected"

TESTS_FOLDER = "tests"

VISUAL_METADATA_FILES = (
    "cap.json",
    "knowledge.json",
    "history.json",
    "evaluation.json",
    "provenance.json",
)

VISUAL_REQUIRED_DIRECTORIES = (
    "canon",
    "metadata",
    "prompts",
    "thumbnails",
    "candidates",
    "rejected",
)

CONFIGURATION_REQUIRED_FILES = (
    "profile.json",
    "description.md",
)

BEHAVIOUR_REQUIRED_DIRECTORIES = (
    "prompts",
    "tests",
)

BEHAVIOUR_REQUIRED_FILES = ("behaviour.json",)

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".tif",
    ".tiff",
}


# =============================================================================
# Validation Severity
# =============================================================================


class ValidationSeverity(Enum):
    """Severity of a validation message."""

    INFO = "info"

    WARNING = "warning"

    ERROR = "error"

    CRITICAL = "critical"


# =============================================================================
# Validation Codes
# =============================================================================


class ValidationCode(Enum):
    """Stable validation identifiers."""

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


# =============================================================================
# Diagnostics
# =============================================================================


@dataclass(slots=True)
class ValidationDiagnostic:
    """
    Single validation result.
    """

    severity: ValidationSeverity

    code: ValidationCode

    asset_id: str | None

    path: Path | None

    message: str

    details: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Asset Validation Result
# =============================================================================


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


# =============================================================================
# Repository Validation Result
# =============================================================================


@dataclass(slots=True)
class RepositoryValidationResult:
    repository: AssetRepositoryInfo | None

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


# =============================================================================
# Validator
# =============================================================================


class CarRepositoryValidator:
    """
    Canonical Asset Repository validator.

    This class performs a complete read-only inspection of a CAR
    repository and produces detailed diagnostics describing
    repository health.

    The validator never writes to disk.
    """

    def __init__(self, repository: Path):

        self.repository = Path(repository)

        self.scanner = AssetRepositoryScanner(self.repository)

        self.scan_result: RepositoryScanResult | None = None

        self.result: RepositoryValidationResult | None = None

        self._asset_ids: set[str] = set()

        self._file_hashes: dict[str, list[str]] = {}

    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_sha256(path: Path) -> str:
        """
        Calculate SHA256 hash of a file.
        """

        sha = hashlib.sha256()

        with path.open("rb") as f:
            while True:
                chunk = f.read(65536)

                if not chunk:
                    break

                sha.update(chunk)

        return sha.hexdigest()

    # -------------------------------------------------------------------------

    @staticmethod
    def load_json(path: Path) -> dict | None:
        """
        Safe JSON loader.
        """

        try:
            with path.open(
                "r",
                encoding="utf-8",
            ) as f:
                return json.load(f)

        except Exception:
            LOGGER.exception(
                "Unable to read JSON %s",
                path,
            )

            return None

    # -------------------------------------------------------------------------

    def validate(self) -> RepositoryValidationResult:
        """
        Public entry point.

        Full implementation continues in Part 2.
        """
        raise NotImplementedError("Implemented in Phase 12.1.1 Part 2.")

    # -------------------------------------------------------------------------

    def validate_repository(self) -> None:
        """
        Validate repository structure.

        Implemented in Part 2.
        """
        raise NotImplementedError()

    # -------------------------------------------------------------------------

    def validate_asset(self, asset) -> AssetValidationResult:
        """
        Validate one asset.

        Implemented in Part 2.
        """
        raise NotImplementedError()

    # -------------------------------------------------------------------------

    def calculate_health(self) -> float:
        """
        Compute repository health score.

        Implemented in Part 5.
        """
        raise NotImplementedError()

    # -------------------------------------------------------------------------

    def validate(self) -> RepositoryValidationResult:
        """
        Perform a complete repository validation.

        Returns
        -------
        RepositoryValidationResult
            Complete validation report.
        """

        LOGGER.info("Starting CAR repository validation: %s", self.repository)

        self.scan_result = self.scanner.scan()

        self.result = RepositoryValidationResult(repository=self.scan_result.repository)

        self.result.total_assets = len(self.scan_result.assets)

        #
        # Repository validation
        #
        self.validate_repository()

        #
        # Asset validation
        #
        for asset in self.scan_result.assets:
            asset_result = self.validate_asset(asset)

            self.result.assets.append(asset_result)

            if asset_result.passed:
                self.result.passed_assets += 1
            else:
                self.result.failed_assets += 1

        #
        # Count diagnostics
        #
        for diagnostic in self.result.diagnostics:
            if diagnostic.severity == ValidationSeverity.WARNING:
                self.result.warnings += 1

            elif diagnostic.severity == ValidationSeverity.ERROR:
                self.result.errors += 1

            elif diagnostic.severity == ValidationSeverity.CRITICAL:
                self.result.critical += 1

        for asset in self.result.assets:
            for diagnostic in asset.diagnostics:
                if diagnostic.severity == ValidationSeverity.WARNING:
                    self.result.warnings += 1

                elif diagnostic.severity == ValidationSeverity.ERROR:
                    self.result.errors += 1

                elif diagnostic.severity == ValidationSeverity.CRITICAL:
                    self.result.critical += 1

        self.result.repository_health = self.calculate_health()

        self.result.passed = self.result.critical == 0 and self.result.errors == 0

        LOGGER.info(
            "Repository validation complete (%s assets)",
            self.result.total_assets,
        )

        return self.result

    # -------------------------------------------------------------------------

    def validate_repository(self) -> None:
        """
        Validate repository-level integrity.
        """

        if self.scan_result is None:
            raise RuntimeError("Repository has not been scanned.")

        repository = self.scan_result.repository

        if repository is None:
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.CRITICAL,
                    code=ValidationCode.INVALID_REPOSITORY,
                    asset_id=None,
                    path=self.repository,
                    message="Repository information unavailable.",
                )
            )

            return

        #
        # Repository existence
        #
        if not self.repository.exists():
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.CRITICAL,
                    code=ValidationCode.INVALID_REPOSITORY,
                    asset_id=None,
                    path=self.repository,
                    message="Repository directory does not exist.",
                )
            )

            return

        #
        # Version validation
        #
        if repository.version != REPOSITORY_VERSION:
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.INVALID_REPOSITORY,
                    asset_id=None,
                    path=self.repository,
                    message=(
                        f"Repository version "
                        f"{repository.version} differs from "
                        f"expected {REPOSITORY_VERSION}."
                    ),
                    details={
                        "expected": REPOSITORY_VERSION,
                        "actual": repository.version,
                    },
                )
            )

        #
        # Scanner issues
        #
        for issue in self.scan_result.issues:
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.UNKNOWN,
                    asset_id=None,
                    path=self.repository,
                    message=str(issue),
                )
            )

    # -------------------------------------------------------------------------

    def validate_asset(self, asset) -> AssetValidationResult:
        """
        Validate a single asset.

        Parameters
        ----------
        asset
            Asset returned by the repository scanner.

        Returns
        -------
        AssetValidationResult
        """

        result = AssetValidationResult(
            asset_id=asset.asset_id,
            asset_class=asset.asset_class,
            asset_path=asset.path,
        )

        #
        # Duplicate Asset ID detection
        #
        if asset.asset_id in self._asset_ids:
            result.passed = False

            self.result.duplicate_asset_ids.add(asset.asset_id)

            result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.DUPLICATE_ASSET_ID,
                    asset_id=asset.asset_id,
                    path=asset.path,
                    message="Duplicate asset identifier.",
                )
            )

        else:
            self._asset_ids.add(asset.asset_id)

        #
        # Asset directory exists
        #
        if not asset.path.exists():
            result.passed = False

            result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.CRITICAL,
                    code=ValidationCode.INVALID_REPOSITORY,
                    asset_id=asset.asset_id,
                    path=asset.path,
                    message="Asset directory does not exist.",
                )
            )

            return result

        #
        # Dispatch by asset class
        #
        if asset.asset_class == AssetClass.VISUAL:
            self._validate_visual_asset(asset, result)

        elif asset.asset_class == AssetClass.CONFIGURATION:
            self._validate_configuration_asset(asset, result)

        elif asset.asset_class == AssetClass.BEHAVIOUR:
            self._validate_behaviour_asset(asset, result)

        else:
            result.passed = False

            result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.UNKNOWN_ASSET_CLASS,
                    asset_id=asset.asset_id,
                    path=asset.path,
                    message="Unknown asset class.",
                )
            )

        return result

    # -------------------------------------------------------------------------
    # Validation dispatch methods
    #
    # Implemented in subsequent phases.
    # -------------------------------------------------------------------------

    def _validate_visual_asset(self, asset, result) -> None:
        raise NotImplementedError("Implemented in Phase 12.1.1 Part 3.")

    # -------------------------------------------------------------------------

    def _validate_configuration_asset(self, asset, result) -> None:
        raise NotImplementedError("Implemented in Phase 12.1.1 Part 4.")

    # -------------------------------------------------------------------------

    def _validate_behaviour_asset(self, asset, result) -> None:
        raise NotImplementedError("Implemented in Phase 12.1.1 Part 4.")

    # -------------------------------------------------------------------------

    def _validate_visual_asset(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate a visual CAR asset.

        Visual assets are expected to contain:

        * manifest.json
        * canon/
        * metadata/
        * prompts/
        * thumbnails/
        * candidates/
        * rejected/

        The metadata directory must contain the files defined by
        ``VISUAL_METADATA_FILES``.

        At least one supported canonical image must exist in ``canon/``.

        Parameters
        ----------
        asset
            Asset record returned by ``AssetRepositoryScanner``.

        result
            Mutable validation result for the current asset.
        """

        asset_path = Path(asset.path)

        LOGGER.debug(
            "Validating visual asset %s at %s",
            asset.asset_id,
            asset_path,
        )

        self._validate_visual_directories(
            asset=asset,
            result=result,
        )

        self._validate_visual_manifest(
            asset=asset,
            result=result,
        )

        self._validate_visual_metadata(
            asset=asset,
            result=result,
        )

        self._validate_canonical_images(
            asset=asset,
            result=result,
        )

        self._validate_visual_prompts(
            asset=asset,
            result=result,
        )

    # -------------------------------------------------------------------------

    def _validate_visual_directories(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate required directories for a visual asset.
        """

        asset_path = Path(asset.path)

        for directory_name in VISUAL_REQUIRED_DIRECTORIES:
            directory_path = asset_path / directory_name

            if not directory_path.exists():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_DIRECTORY,
                    path=directory_path,
                    message=(f"Required visual asset directory '{directory_name}' is missing."),
                    details={
                        "directory": directory_name,
                    },
                )

                continue

            if not directory_path.is_dir():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_DIRECTORY,
                    path=directory_path,
                    message=(f"Required path '{directory_name}' exists but is not a directory."),
                    details={
                        "directory": directory_name,
                        "expected_type": "directory",
                    },
                )

    # -------------------------------------------------------------------------

    def _validate_visual_manifest(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate the visual asset manifest.
        """

        manifest_path = Path(asset.path) / DEFAULT_MANIFEST

        if not manifest_path.exists():
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.MISSING_FILE,
                path=manifest_path,
                message="Visual asset manifest.json is missing.",
                details={
                    "required_file": DEFAULT_MANIFEST,
                },
            )

            return

        if not manifest_path.is_file():
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_MANIFEST,
                path=manifest_path,
                message="manifest.json exists but is not a file.",
            )

            return

        manifest = self._load_json_for_asset(
            path=manifest_path,
            result=result,
            invalid_code=ValidationCode.INVALID_MANIFEST,
            description="visual asset manifest",
        )

        if manifest is None:
            return

        if not isinstance(manifest, dict):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_MANIFEST,
                path=manifest_path,
                message="Visual asset manifest must contain a JSON object.",
                details={
                    "actual_type": type(manifest).__name__,
                },
            )

            return

        self._validate_declared_asset_id(
            asset=asset,
            result=result,
            document=manifest,
            document_path=manifest_path,
            document_name="manifest",
        )

        self._record_file_hash(
            path=manifest_path,
            result=result,
            detect_duplicates=False,
        )

    # -------------------------------------------------------------------------

    def _validate_visual_metadata(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate required visual metadata files.
        """

        metadata_directory = Path(asset.path) / METADATA_FOLDER

        if not metadata_directory.exists():
            return

        if not metadata_directory.is_dir():
            return

        for metadata_name in VISUAL_METADATA_FILES:
            metadata_path = metadata_directory / metadata_name

            if not metadata_path.exists():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_METADATA,
                    path=metadata_path,
                    message=(f"Required visual metadata file '{metadata_name}' is missing."),
                    details={
                        "required_file": metadata_name,
                    },
                )

                continue

            if not metadata_path.is_file():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_METADATA,
                    path=metadata_path,
                    message=(f"Metadata path '{metadata_name}' exists but is not a file."),
                    details={
                        "required_file": metadata_name,
                        "expected_type": "file",
                    },
                )

                continue

            metadata = self._load_json_for_asset(
                path=metadata_path,
                result=result,
                invalid_code=ValidationCode.INVALID_SCHEMA,
                description=f"metadata file '{metadata_name}'",
            )

            if metadata is None:
                continue

            if not isinstance(metadata, dict):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_SCHEMA,
                    path=metadata_path,
                    message=(f"Metadata file '{metadata_name}' must contain a JSON object."),
                    details={
                        "actual_type": type(metadata).__name__,
                    },
                )

                continue

            result.metadata_count += 1

            self._validate_declared_asset_id(
                asset=asset,
                result=result,
                document=metadata,
                document_path=metadata_path,
                document_name=metadata_name,
            )

            self._record_file_hash(
                path=metadata_path,
                result=result,
                detect_duplicates=False,
            )

    # -------------------------------------------------------------------------

    def _validate_canonical_images(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate canonical images for a visual asset.

        A visual asset must contain at least one supported image in its
        ``canon`` directory. Images may be stored in nested directories.
        """

        canon_directory = Path(asset.path) / CANON_FOLDER

        if not canon_directory.exists():
            return

        if not canon_directory.is_dir():
            return

        canonical_images = sorted(
            path
            for path in canon_directory.rglob("*")
            if (path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS)
        )

        result.image_count = len(canonical_images)

        if not canonical_images:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.MISSING_CANONICAL_IMAGE,
                path=canon_directory,
                message=("Visual asset does not contain a supported canonical image."),
                details={
                    "supported_extensions": sorted(SUPPORTED_IMAGE_EXTENSIONS),
                },
            )

            return

        for image_path in canonical_images:
            try:
                if image_path.stat().st_size == 0:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.MISSING_CANONICAL_IMAGE,
                        path=image_path,
                        message="Canonical image file is empty.",
                    )

                    continue

            except OSError as exc:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_CANONICAL_IMAGE,
                    path=image_path,
                    message="Canonical image could not be inspected.",
                    details={
                        "error": str(exc),
                    },
                )

                continue

            self._record_file_hash(
                path=image_path,
                result=result,
                detect_duplicates=True,
            )

    # -------------------------------------------------------------------------

    def _validate_visual_prompts(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Inspect the visual asset prompt directory.

        An empty prompt directory is currently reported as a warning rather
        than an error because migrated legacy assets may not yet have prompt
        packages.
        """

        prompts_directory = Path(asset.path) / PROMPTS_FOLDER

        if not prompts_directory.exists():
            return

        if not prompts_directory.is_dir():
            return

        prompt_files = sorted(path for path in prompts_directory.rglob("*") if path.is_file())

        result.prompt_count = len(prompt_files)

        if not prompt_files:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.EMPTY_DIRECTORY,
                path=prompts_directory,
                message="Visual asset prompt directory is empty.",
                details={
                    "directory": PROMPTS_FOLDER,
                },
            )

            return

        for prompt_path in prompt_files:
            try:
                if prompt_path.stat().st_size == 0:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.WARNING,
                        code=ValidationCode.EMPTY_DIRECTORY,
                        path=prompt_path,
                        message="Visual asset prompt file is empty.",
                    )

            except OSError as exc:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.UNUSED_FILE,
                    path=prompt_path,
                    message="Prompt file could not be inspected.",
                    details={
                        "error": str(exc),
                    },
                )

                continue

            if prompt_path.suffix.lower() == ".json":
                prompt_data = self._load_json_for_asset(
                    path=prompt_path,
                    result=result,
                    invalid_code=ValidationCode.INVALID_JSON,
                    description="visual prompt JSON",
                )

                if prompt_data is not None:
                    self._validate_declared_asset_id(
                        asset=asset,
                        result=result,
                        document=prompt_data,
                        document_path=prompt_path,
                        document_name=prompt_path.name,
                    )

            self._record_file_hash(
                path=prompt_path,
                result=result,
                detect_duplicates=False,
            )

    # -------------------------------------------------------------------------
    # Shared validation helpers
    # -------------------------------------------------------------------------

    def _add_asset_diagnostic(
        self,
        result: AssetValidationResult,
        severity: ValidationSeverity,
        code: ValidationCode,
        path: Path | None,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a diagnostic to an asset result.

        Error and critical diagnostics automatically mark the asset as failed.
        """

        diagnostic = ValidationDiagnostic(
            severity=severity,
            code=code,
            asset_id=result.asset_id,
            path=path,
            message=message,
            details=details or {},
        )

        result.diagnostics.append(diagnostic)

        if severity in {
            ValidationSeverity.ERROR,
            ValidationSeverity.CRITICAL,
        }:
            result.passed = False

    # -------------------------------------------------------------------------

    def _load_json_for_asset(
        self,
        path: Path,
        result: AssetValidationResult,
        invalid_code: ValidationCode,
        description: str,
    ) -> Any | None:
        """
        Load JSON while recording detailed asset diagnostics.

        This helper differs from ``load_json`` because it records the exact
        exception in the validation result instead of only logging it.
        """

        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        except json.JSONDecodeError as exc:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=invalid_code,
                path=path,
                message=f"Invalid JSON in {description}.",
                details={
                    "line": exc.lineno,
                    "column": exc.colno,
                    "position": exc.pos,
                    "error": exc.msg,
                },
            )

        except UnicodeDecodeError as exc:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=invalid_code,
                path=path,
                message=f"{description.capitalize()} is not valid UTF-8.",
                details={
                    "error": str(exc),
                },
            )

        except OSError as exc:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=invalid_code,
                path=path,
                message=f"Unable to read {description}.",
                details={
                    "error": str(exc),
                },
            )

        return None

    # -------------------------------------------------------------------------

    def _validate_declared_asset_id(
        self,
        asset,
        result: AssetValidationResult,
        document: Any,
        document_path: Path,
        document_name: str,
    ) -> None:
        """
        Validate an asset ID declared inside a JSON document.

        Documents are not required to declare an asset ID at this stage.
        When one is present, however, it must match the scanner's asset ID.

        Supported field names are:

        * asset_id
        * assetId
        * id
        """

        if not isinstance(document, dict):
            return

        declared_asset_id = None
        declared_field = None

        for field_name in ("asset_id", "assetId", "id"):
            value = document.get(field_name)

            if value is not None:
                declared_asset_id = str(value).strip()
                declared_field = field_name
                break

        if declared_asset_id is None:
            return

        expected_asset_id = str(asset.asset_id).strip()

        if declared_asset_id != expected_asset_id:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_SCHEMA,
                path=document_path,
                message=(
                    f"Asset ID declared in {document_name} does not match the repository asset ID."
                ),
                details={
                    "field": declared_field,
                    "expected": expected_asset_id,
                    "actual": declared_asset_id,
                },
            )

    # -------------------------------------------------------------------------

    def _record_file_hash(
        self,
        path: Path,
        result: AssetValidationResult,
        detect_duplicates: bool,
    ) -> str | None:
        """
        Calculate and record a file SHA-256 hash.

        Parameters
        ----------
        path
            File to hash.

        result
            Asset result receiving the hash.

        detect_duplicates
            When true, matching hashes found in other files are reported as
            duplicate-content warnings.

        Returns
        -------
        Optional[str]
            SHA-256 hash, or ``None`` when hashing failed.
        """

        try:
            file_hash = self.calculate_sha256(path)

        except OSError as exc:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.UNKNOWN,
                path=path,
                message="Unable to calculate file hash.",
                details={
                    "error": str(exc),
                },
            )

            return None

        try:
            relative_path = str(path.relative_to(self.repository))

        except ValueError:
            relative_path = str(path)

        result.file_hashes[relative_path] = file_hash

        known_paths = self._file_hashes.setdefault(
            file_hash,
            [],
        )

        if detect_duplicates and known_paths:
            duplicate_paths = [*known_paths, relative_path]

            if self.result is not None:
                repository_duplicates = self.result.duplicate_hashes.setdefault(
                    file_hash,
                    [],
                )

                for duplicate_path in duplicate_paths:
                    if duplicate_path not in repository_duplicates:
                        repository_duplicates.append(duplicate_path)

            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.DUPLICATE_HASH,
                path=path,
                message=("Canonical image has the same content hash as another canonical image."),
                details={
                    "sha256": file_hash,
                    "matching_files": duplicate_paths,
                },
            )

        if relative_path not in known_paths:
            known_paths.append(relative_path)

        return file_hash

    # -------------------------------------------------------------------------

    def _validate_configuration_asset(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate a CAR configuration asset.

        Configuration assets are expected to contain:

        * profile.json
        * description.md

        A configuration asset does not require a visual manifest, canonical
        images, candidate images, thumbnails, or rejected-image folders.

        Parameters
        ----------
        asset
            Asset record returned by ``AssetRepositoryScanner``.

        result
            Mutable validation result for the current asset.
        """

        asset_path = Path(asset.path)

        LOGGER.debug(
            "Validating configuration asset %s at %s",
            asset.asset_id,
            asset_path,
        )

        self._validate_configuration_required_files(
            asset=asset,
            result=result,
        )

        self._validate_configuration_profile(
            asset=asset,
            result=result,
        )

        self._validate_configuration_description(
            asset=asset,
            result=result,
        )

    # -------------------------------------------------------------------------

    def _validate_configuration_required_files(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate the required files for a configuration asset.
        """

        asset_path = Path(asset.path)

        for file_name in CONFIGURATION_REQUIRED_FILES:
            file_path = asset_path / file_name

            if not file_path.exists():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_FILE,
                    path=file_path,
                    message=(f"Required configuration file '{file_name}' is missing."),
                    details={
                        "required_file": file_name,
                    },
                )

                continue

            if not file_path.is_file():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_FILE,
                    path=file_path,
                    message=(
                        f"Required configuration path '{file_name}' exists but is not a file."
                    ),
                    details={
                        "required_file": file_name,
                        "expected_type": "file",
                    },
                )

    # -------------------------------------------------------------------------

    def _validate_configuration_profile(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate ``profile.json`` for a configuration asset.

        The current verifier intentionally applies a tolerant baseline schema.
        It verifies structural integrity without forcing all existing CAR
        profiles into one domain-specific format.

        Required baseline characteristics:

        * The file must contain valid UTF-8 JSON.
        * The JSON root must be an object.
        * If an asset ID is declared, it must match the repository asset ID.
        * Identity fields, when present, must contain valid scalar values.
        * Reference collections, when present, must use supported structures.
        """

        profile_path = Path(asset.path) / DEFAULT_PROFILE

        if not profile_path.exists() or not profile_path.is_file():
            return

        profile = self._load_json_for_asset(
            path=profile_path,
            result=result,
            invalid_code=ValidationCode.INVALID_PROFILE,
            description="configuration profile",
        )

        if profile is None:
            return

        if not isinstance(profile, dict):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_PROFILE,
                path=profile_path,
                message=("Configuration profile must contain a JSON object at its root."),
                details={
                    "actual_type": type(profile).__name__,
                },
            )

            return

        if not profile:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.INVALID_PROFILE,
                path=profile_path,
                message="Configuration profile is an empty JSON object.",
            )

        self._validate_declared_asset_id(
            asset=asset,
            result=result,
            document=profile,
            document_path=profile_path,
            document_name=DEFAULT_PROFILE,
        )

        self._validate_configuration_identity_fields(
            profile=profile,
            profile_path=profile_path,
            result=result,
        )

        self._validate_configuration_version(
            profile=profile,
            profile_path=profile_path,
            result=result,
        )

        self._validate_configuration_references(
            profile=profile,
            profile_path=profile_path,
            result=result,
        )

        self._validate_configuration_values(
            value=profile,
            value_path="$",
            profile_path=profile_path,
            result=result,
        )

        result.metadata_count += 1

        self._record_file_hash(
            path=profile_path,
            result=result,
            detect_duplicates=False,
        )

    # -------------------------------------------------------------------------

    def _validate_configuration_identity_fields(
        self,
        profile: dict[str, Any],
        profile_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate commonly used configuration identity fields.

        Configuration profiles may use different domain schemas. The verifier
        therefore validates supported identity fields only when they are
        present instead of requiring all of them.
        """

        string_fields = (
            "name",
            "title",
            "display_name",
            "displayName",
            "category",
            "type",
            "profile_type",
            "profileType",
        )

        for field_name in string_fields:
            if field_name not in profile:
                continue

            value = profile[field_name]

            if not isinstance(value, str):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_PROFILE,
                    path=profile_path,
                    message=(f"Configuration profile field '{field_name}' must be a string."),
                    details={
                        "field": field_name,
                        "actual_type": type(value).__name__,
                    },
                )

                continue

            if not value.strip():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.INVALID_PROFILE,
                    path=profile_path,
                    message=(f"Configuration profile field '{field_name}' is empty."),
                    details={
                        "field": field_name,
                    },
                )

    # -------------------------------------------------------------------------

    def _validate_configuration_version(
        self,
        profile: dict[str, Any],
        profile_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate an optional profile version field.

        Accepted version values are non-empty strings or non-negative integers.
        """

        version_fields = (
            "version",
            "profile_version",
            "profileVersion",
            "schema_version",
            "schemaVersion",
        )

        for field_name in version_fields:
            if field_name not in profile:
                continue

            value = profile[field_name]

            if isinstance(value, bool):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_PROFILE,
                    path=profile_path,
                    message=(f"Configuration version field '{field_name}' cannot be Boolean."),
                    details={
                        "field": field_name,
                        "actual": value,
                    },
                )

                continue

            if isinstance(value, int):
                if value < 0:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_PROFILE,
                        path=profile_path,
                        message=(f"Configuration version field '{field_name}' cannot be negative."),
                        details={
                            "field": field_name,
                            "actual": value,
                        },
                    )

                continue

            if isinstance(value, str):
                if not value.strip():
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.WARNING,
                        code=ValidationCode.INVALID_PROFILE,
                        path=profile_path,
                        message=(f"Configuration version field '{field_name}' is empty."),
                        details={
                            "field": field_name,
                        },
                    )

                continue

            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_PROFILE,
                path=profile_path,
                message=(
                    f"Configuration version field '{field_name}' must be a string or integer."
                ),
                details={
                    "field": field_name,
                    "actual_type": type(value).__name__,
                },
            )

    # -------------------------------------------------------------------------

    def _validate_configuration_references(
        self,
        profile: dict[str, Any],
        profile_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate optional asset-reference collections.

        Supported reference fields may contain:

        * A single asset ID string.
        * A list of asset ID strings.
        * A mapping whose values are asset ID strings or lists of strings.

        Reference existence is checked against scanner results when the
        referenced identifier appears to be a CAR asset ID.
        """

        reference_fields = (
            "asset_reference",
            "assetReference",
            "asset_references",
            "assetReferences",
            "references",
            "depends_on",
            "dependsOn",
            "dependencies",
        )

        known_asset_ids = self._get_scanned_asset_ids()

        for field_name in reference_fields:
            if field_name not in profile:
                continue

            references = self._extract_reference_values(
                value=profile[field_name],
                field_name=field_name,
                profile_path=profile_path,
                result=result,
            )

            for reference in references:
                reference_id = reference.strip()

                if not reference_id:
                    continue

                if not self._looks_like_asset_id(reference_id):
                    continue

                if known_asset_ids and reference_id not in known_asset_ids:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.WARNING,
                        code=ValidationCode.INVALID_PROFILE,
                        path=profile_path,
                        message=(
                            f"Configuration profile references unknown asset '{reference_id}'."
                        ),
                        details={
                            "field": field_name,
                            "reference": reference_id,
                        },
                    )

    # -------------------------------------------------------------------------

    def _extract_reference_values(
        self,
        value: Any,
        field_name: str,
        profile_path: Path,
        result: AssetValidationResult,
    ) -> list[str]:
        """
        Extract string references from a supported reference structure.
        """

        references: list[str] = []

        if value is None:
            return references

        if isinstance(value, str):
            references.append(value)
            return references

        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    references.append(item)

                elif isinstance(item, dict):
                    reference = self._reference_from_mapping(item)

                    if reference is not None:
                        references.append(reference)
                    else:
                        self._add_asset_diagnostic(
                            result=result,
                            severity=ValidationSeverity.WARNING,
                            code=ValidationCode.INVALID_PROFILE,
                            path=profile_path,
                            message=(
                                f"Reference entry "
                                f"'{field_name}[{index}]' does not "
                                f"declare an asset ID."
                            ),
                            details={
                                "field": field_name,
                                "index": index,
                            },
                        )

                else:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_PROFILE,
                        path=profile_path,
                        message=(
                            f"Reference entry '{field_name}[{index}]' must be a string or object."
                        ),
                        details={
                            "field": field_name,
                            "index": index,
                            "actual_type": type(item).__name__,
                        },
                    )

            return references

        if isinstance(value, dict):
            direct_reference = self._reference_from_mapping(value)

            if direct_reference is not None:
                references.append(direct_reference)
                return references

            for key, item in value.items():
                if isinstance(item, str):
                    references.append(item)

                elif isinstance(item, list):
                    for nested_index, nested_item in enumerate(item):
                        if isinstance(nested_item, str):
                            references.append(nested_item)

                        elif isinstance(nested_item, dict):
                            nested_reference = self._reference_from_mapping(nested_item)

                            if nested_reference is not None:
                                references.append(nested_reference)

                            else:
                                self._add_asset_diagnostic(
                                    result=result,
                                    severity=ValidationSeverity.WARNING,
                                    code=ValidationCode.INVALID_PROFILE,
                                    path=profile_path,
                                    message=(
                                        f"Reference entry "
                                        f"'{field_name}.{key}"
                                        f"[{nested_index}]' does not "
                                        f"declare an asset ID."
                                    ),
                                    details={
                                        "field": field_name,
                                        "key": str(key),
                                        "index": nested_index,
                                    },
                                )

                        else:
                            self._add_asset_diagnostic(
                                result=result,
                                severity=ValidationSeverity.ERROR,
                                code=ValidationCode.INVALID_PROFILE,
                                path=profile_path,
                                message=(
                                    f"Reference entry "
                                    f"'{field_name}.{key}"
                                    f"[{nested_index}]' has an "
                                    f"unsupported type."
                                ),
                                details={
                                    "field": field_name,
                                    "key": str(key),
                                    "index": nested_index,
                                    "actual_type": (type(nested_item).__name__),
                                },
                            )

                elif isinstance(item, dict):
                    nested_reference = self._reference_from_mapping(item)

                    if nested_reference is not None:
                        references.append(nested_reference)

                elif item is not None:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_PROFILE,
                        path=profile_path,
                        message=(
                            f"Reference mapping value '{field_name}.{key}' has an unsupported type."
                        ),
                        details={
                            "field": field_name,
                            "key": str(key),
                            "actual_type": type(item).__name__,
                        },
                    )

            return references

        self._add_asset_diagnostic(
            result=result,
            severity=ValidationSeverity.ERROR,
            code=ValidationCode.INVALID_PROFILE,
            path=profile_path,
            message=(f"Configuration reference field '{field_name}' has an unsupported type."),
            details={
                "field": field_name,
                "actual_type": type(value).__name__,
            },
        )

        return references

    # -------------------------------------------------------------------------

    @staticmethod
    def _reference_from_mapping(
        value: dict[str, Any],
    ) -> str | None:
        """
        Extract an asset ID from a reference mapping.
        """

        for field_name in (
            "asset_id",
            "assetId",
            "reference",
            "ref",
            "id",
        ):
            candidate = value.get(field_name)

            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()

        return None

    # -------------------------------------------------------------------------

    def _validate_configuration_values(
        self,
        value: Any,
        value_path: str,
        profile_path: Path,
        result: AssetValidationResult,
        depth: int = 0,
    ) -> None:
        """
        Recursively inspect profile values for unsupported JSON structures.

        Standard JSON parsing already limits values to JSON-compatible types.
        This method provides additional diagnostics for deeply nested or
        suspiciously empty structures.

        The check is deliberately conservative because configuration profiles
        may contain legitimate empty lists or objects as migration templates.
        """

        maximum_depth = 32

        if depth > maximum_depth:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_PROFILE,
                path=profile_path,
                message=("Configuration profile exceeds the maximum supported nesting depth."),
                details={
                    "json_path": value_path,
                    "maximum_depth": maximum_depth,
                },
            )

            return

        if isinstance(value, dict):
            for key, child_value in value.items():
                if not isinstance(key, str):
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_PROFILE,
                        path=profile_path,
                        message=("Configuration object contains a non-string key."),
                        details={
                            "json_path": value_path,
                            "actual_type": type(key).__name__,
                        },
                    )

                    continue

                child_path = f"{value_path}.{key}"

                self._validate_configuration_values(
                    value=child_value,
                    value_path=child_path,
                    profile_path=profile_path,
                    result=result,
                    depth=depth + 1,
                )

            return

        if isinstance(value, list):
            for index, child_value in enumerate(value):
                child_path = f"{value_path}[{index}]"

                self._validate_configuration_values(
                    value=child_value,
                    value_path=child_path,
                    profile_path=profile_path,
                    result=result,
                    depth=depth + 1,
                )

            return

        if isinstance(value, float):
            if value != value:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_PROFILE,
                    path=profile_path,
                    message=("Configuration profile contains a NaN numeric value."),
                    details={
                        "json_path": value_path,
                    },
                )

            elif value in (float("inf"), float("-inf")):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_PROFILE,
                    path=profile_path,
                    message=("Configuration profile contains an infinite numeric value."),
                    details={
                        "json_path": value_path,
                        "actual": str(value),
                    },
                )

    # -------------------------------------------------------------------------

    def _validate_configuration_description(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate ``description.md`` for a configuration asset.
        """

        description_path = Path(asset.path) / DEFAULT_DESCRIPTION

        if not description_path.exists() or not description_path.is_file():
            return

        try:
            description = description_path.read_text(encoding="utf-8")

        except UnicodeDecodeError as exc:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_SCHEMA,
                path=description_path,
                message=("Configuration description is not valid UTF-8."),
                details={
                    "error": str(exc),
                },
            )

            return

        except OSError as exc:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.MISSING_FILE,
                path=description_path,
                message="Unable to read configuration description.",
                details={
                    "error": str(exc),
                },
            )

            return

        stripped_description = description.strip()

        if not stripped_description:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.EMPTY_DIRECTORY,
                path=description_path,
                message="Configuration description is empty.",
            )

        elif len(stripped_description) < 20:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.INVALID_SCHEMA,
                path=description_path,
                message=("Configuration description is unusually short."),
                details={
                    "character_count": len(stripped_description),
                    "recommended_minimum": 20,
                },
            )

        if "\x00" in description:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_SCHEMA,
                path=description_path,
                message=("Configuration description contains null characters."),
            )

        self._record_file_hash(
            path=description_path,
            result=result,
            detect_duplicates=False,
        )

    # -------------------------------------------------------------------------
    # Configuration validation helpers
    # -------------------------------------------------------------------------

    def _get_scanned_asset_ids(self) -> set[str]:
        """
        Return all asset IDs discovered by the current repository scan.
        """

        if self.scan_result is None:
            return set()

        return {
            str(asset.asset_id).strip()
            for asset in self.scan_result.assets
            if getattr(asset, "asset_id", None) is not None
        }

    # -------------------------------------------------------------------------

    @staticmethod
    def _looks_like_asset_id(value: str) -> bool:
        """
        Determine whether a string resembles a CAR asset identifier.

        Examples include:

        * CAP-CHR-001
        * CAP-CAM-004
        * CAP-LGT-002
        * CAR-ENV-001

        The test is intentionally generic and does not hard-code every
        repository category.
        """

        candidate = value.strip()

        if not candidate:
            return False

        parts = candidate.split("-")

        if len(parts) < 3:
            return False

        if not all(parts):
            return False

        prefix = parts[0]

        if not prefix.isalpha():
            return False

        return any(character.isdigit() for character in parts[-1])

    # -------------------------------------------------------------------------

    def _validate_behaviour_asset(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate the core structure and definition of a behaviour asset.

        Behaviour assets describe reusable production logic, automation,
        processing rules, evaluators, generators, or pipeline actions.

        Required structure:

        * behaviour.json
        * prompts/
        * tests/

        Prompt-package content, test content, and executable module inspection
        are implemented in Phase 12.1.1 Part 4B2.

        Parameters
        ----------
        asset
            Asset record returned by ``AssetRepositoryScanner``.

        result
            Mutable validation result for the current asset.
        """

        asset_path = Path(asset.path)

        LOGGER.debug(
            "Validating behaviour asset %s at %s",
            asset.asset_id,
            asset_path,
        )

        self._validate_behaviour_required_structure(
            asset=asset,
            result=result,
        )

        self._validate_behaviour_definition(
            asset=asset,
            result=result,
        )

        # These methods are implemented in Part 4B2.
        self._validate_behaviour_prompts(
            asset=asset,
            result=result,
        )

        self._validate_behaviour_tests(
            asset=asset,
            result=result,
        )

    # -------------------------------------------------------------------------

    def _validate_behaviour_required_structure(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate required files and directories for a behaviour asset.
        """

        asset_path = Path(asset.path)

        for directory_name in BEHAVIOUR_REQUIRED_DIRECTORIES:
            directory_path = asset_path / directory_name

            if not directory_path.exists():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_DIRECTORY,
                    path=directory_path,
                    message=(f"Required behaviour directory '{directory_name}' is missing."),
                    details={
                        "directory": directory_name,
                    },
                )

                continue

            if not directory_path.is_dir():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_DIRECTORY,
                    path=directory_path,
                    message=(
                        f"Required behaviour path '{directory_name}' exists but is not a directory."
                    ),
                    details={
                        "directory": directory_name,
                        "expected_type": "directory",
                    },
                )

        for file_name in BEHAVIOUR_REQUIRED_FILES:
            file_path = asset_path / file_name

            if not file_path.exists():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_FILE,
                    path=file_path,
                    message=(f"Required behaviour file '{file_name}' is missing."),
                    details={
                        "required_file": file_name,
                    },
                )

                continue

            if not file_path.is_file():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.MISSING_FILE,
                    path=file_path,
                    message=(f"Required behaviour path '{file_name}' exists but is not a file."),
                    details={
                        "required_file": file_name,
                        "expected_type": "file",
                    },
                )

    # -------------------------------------------------------------------------

    def _validate_behaviour_definition(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate the root ``behaviour.json`` definition.

        The baseline behaviour schema is intentionally broad enough to support
        different VSCS production behaviours while still enforcing reliable
        identity, execution, dependency, and configuration structures.
        """

        behaviour_path = Path(asset.path) / DEFAULT_BEHAVIOUR

        if not behaviour_path.exists() or not behaviour_path.is_file():
            return

        behaviour = self._load_json_for_asset(
            path=behaviour_path,
            result=result,
            invalid_code=ValidationCode.INVALID_BEHAVIOUR,
            description="behaviour definition",
        )

        if behaviour is None:
            return

        if not isinstance(behaviour, dict):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=("Behaviour definition must contain a JSON object at its root."),
                details={
                    "actual_type": type(behaviour).__name__,
                },
            )

            return

        if not behaviour:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message="Behaviour definition is an empty JSON object.",
            )

            return

        self._validate_declared_asset_id(
            asset=asset,
            result=result,
            document=behaviour,
            document_path=behaviour_path,
            document_name=DEFAULT_BEHAVIOUR,
        )

        self._validate_behaviour_identity(
            behaviour=behaviour,
            behaviour_path=behaviour_path,
            result=result,
        )

        self._validate_behaviour_version(
            behaviour=behaviour,
            behaviour_path=behaviour_path,
            result=result,
        )

        self._validate_behaviour_entry_point(
            behaviour=behaviour,
            behaviour_path=behaviour_path,
            asset_path=Path(asset.path),
            result=result,
        )

        self._validate_behaviour_execution_settings(
            behaviour=behaviour,
            behaviour_path=behaviour_path,
            result=result,
        )

        self._validate_behaviour_dependencies(
            behaviour=behaviour,
            behaviour_path=behaviour_path,
            result=result,
        )

        result.metadata_count += 1

        self._record_file_hash(
            path=behaviour_path,
            result=result,
            detect_duplicates=False,
        )

    # -------------------------------------------------------------------------

    def _validate_behaviour_identity(
        self,
        behaviour: dict[str, Any],
        behaviour_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate behaviour identity and classification fields.
        """

        optional_string_fields = (
            "name",
            "title",
            "display_name",
            "displayName",
            "description",
            "category",
            "type",
            "behaviour_type",
            "behaviourType",
            "provider",
            "engine",
        )

        identity_fields_found = 0

        for field_name in optional_string_fields:
            if field_name not in behaviour:
                continue

            identity_fields_found += 1
            value = behaviour[field_name]

            if not isinstance(value, str):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Behaviour field '{field_name}' must be a string."),
                    details={
                        "field": field_name,
                        "actual_type": type(value).__name__,
                    },
                )

                continue

            if not value.strip():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Behaviour field '{field_name}' is empty."),
                    details={
                        "field": field_name,
                    },
                )

        if identity_fields_found == 0:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=(
                    "Behaviour definition does not contain a descriptive "
                    "identity field such as name, title, type, or category."
                ),
            )

        enabled = behaviour.get("enabled")

        if enabled is not None and not isinstance(enabled, bool):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message="Behaviour field 'enabled' must be Boolean.",
                details={
                    "field": "enabled",
                    "actual_type": type(enabled).__name__,
                },
            )

    # -------------------------------------------------------------------------

    def _validate_behaviour_version(
        self,
        behaviour: dict[str, Any],
        behaviour_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate optional behaviour or schema version fields.
        """

        version_fields = (
            "version",
            "behaviour_version",
            "behaviourVersion",
            "schema_version",
            "schemaVersion",
        )

        for field_name in version_fields:
            if field_name not in behaviour:
                continue

            value = behaviour[field_name]

            if isinstance(value, bool):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Behaviour version field '{field_name}' cannot be Boolean."),
                    details={
                        "field": field_name,
                        "actual": value,
                    },
                )

                continue

            if isinstance(value, int):
                if value < 0:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_BEHAVIOUR,
                        path=behaviour_path,
                        message=(f"Behaviour version field '{field_name}' cannot be negative."),
                        details={
                            "field": field_name,
                            "actual": value,
                        },
                    )

                continue

            if isinstance(value, str):
                if not value.strip():
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.WARNING,
                        code=ValidationCode.INVALID_BEHAVIOUR,
                        path=behaviour_path,
                        message=(f"Behaviour version field '{field_name}' is empty."),
                        details={
                            "field": field_name,
                        },
                    )

                continue

            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=(f"Behaviour version field '{field_name}' must be a string or integer."),
                details={
                    "field": field_name,
                    "actual_type": type(value).__name__,
                },
            )

    # -------------------------------------------------------------------------

    def _validate_behaviour_entry_point(
        self,
        behaviour: dict[str, Any],
        behaviour_path: Path,
        asset_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate an optional behaviour entry point.

        Supported forms include:

        * ``module:function``
        * ``package.module:function``
        * Relative script path such as ``scripts/process.py``
        * Object form containing module, function, callable, or path fields

        Full executable-module inspection is deferred to Part 4B2.
        """

        entry_field = None
        entry_value: Any = None

        for field_name in (
            "entry_point",
            "entryPoint",
            "handler",
            "callable",
            "module",
            "script",
        ):
            if field_name in behaviour:
                entry_field = field_name
                entry_value = behaviour[field_name]
                break

        if entry_field is None:
            return

        if isinstance(entry_value, str):
            entry_value = entry_value.strip()

            if not entry_value:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Behaviour entry-point field '{entry_field}' is empty."),
                    details={
                        "field": entry_field,
                    },
                )

                return

            self._validate_behaviour_entry_point_string(
                entry_value=entry_value,
                entry_field=entry_field,
                behaviour_path=behaviour_path,
                asset_path=asset_path,
                result=result,
            )

            return

        if isinstance(entry_value, dict):
            supported_fields = (
                "module",
                "function",
                "callable",
                "handler",
                "path",
                "script",
            )

            declared_values = {
                key: value for key, value in entry_value.items() if key in supported_fields
            }

            if not declared_values:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(
                        "Behaviour entry-point object does not contain "
                        "a supported module, function, callable, or path."
                    ),
                    details={
                        "field": entry_field,
                    },
                )

                return

            for field_name, value in declared_values.items():
                if not isinstance(value, str) or not value.strip():
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_BEHAVIOUR,
                        path=behaviour_path,
                        message=(
                            f"Behaviour entry-point property "
                            f"'{field_name}' must be a non-empty string."
                        ),
                        details={
                            "field": f"{entry_field}.{field_name}",
                            "actual_type": type(value).__name__,
                        },
                    )

            path_value = entry_value.get("path") or entry_value.get("script")

            if isinstance(path_value, str) and path_value.strip():
                self._validate_behaviour_relative_path(
                    declared_path=path_value.strip(),
                    behaviour_path=behaviour_path,
                    asset_path=asset_path,
                    result=result,
                )

            return

        self._add_asset_diagnostic(
            result=result,
            severity=ValidationSeverity.ERROR,
            code=ValidationCode.INVALID_BEHAVIOUR,
            path=behaviour_path,
            message=(f"Behaviour entry-point field '{entry_field}' must be a string or object."),
            details={
                "field": entry_field,
                "actual_type": type(entry_value).__name__,
            },
        )

    # -------------------------------------------------------------------------

    def _validate_behaviour_entry_point_string(
        self,
        entry_value: str,
        entry_field: str,
        behaviour_path: Path,
        asset_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate a string-form behaviour entry point.
        """

        looks_like_path = (
            "/" in entry_value
            or "\\" in entry_value
            or entry_value.lower().endswith((".py", ".ps1", ".js", ".ts", ".bat", ".cmd"))
        )

        if looks_like_path:
            self._validate_behaviour_relative_path(
                declared_path=entry_value,
                behaviour_path=behaviour_path,
                asset_path=asset_path,
                result=result,
            )

            return

        if ":" in entry_value:
            module_name, callable_name = entry_value.rsplit(":", 1)

            if not module_name.strip() or not callable_name.strip():
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=("Behaviour module entry point must use the format 'module:callable'."),
                    details={
                        "field": entry_field,
                        "actual": entry_value,
                    },
                )

            return

        if entry_field in {"handler", "callable"}:
            return

        if "." not in entry_value:
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=(
                    "Behaviour entry point does not appear to be a "
                    "module path, module:callable pair, or script path."
                ),
                details={
                    "field": entry_field,
                    "actual": entry_value,
                },
            )

    # -------------------------------------------------------------------------

    def _validate_behaviour_relative_path(
        self,
        declared_path: str,
        behaviour_path: Path,
        asset_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate a path declared by the behaviour definition.

        Absolute paths and paths escaping the asset directory are rejected.
        """

        normalised_value = declared_path.replace("\\", "/")
        relative_path = Path(normalised_value)

        if relative_path.is_absolute():
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message="Behaviour entry point must not use an absolute path.",
                details={
                    "declared_path": declared_path,
                },
            )

            return

        candidate_path = asset_path / relative_path

        try:
            resolved_asset_path = asset_path.resolve()
            resolved_candidate = candidate_path.resolve()

            resolved_candidate.relative_to(resolved_asset_path)

        except (OSError, ValueError):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=("Behaviour entry-point path escapes the asset directory."),
                details={
                    "declared_path": declared_path,
                },
            )

            return

        if not candidate_path.exists():
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.WARNING,
                code=ValidationCode.MISSING_FILE,
                path=candidate_path,
                message=("Behaviour entry-point file does not currently exist."),
                details={
                    "declared_path": declared_path,
                },
            )

        elif not candidate_path.is_file():
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=candidate_path,
                message=("Behaviour entry-point path exists but is not a file."),
                details={
                    "declared_path": declared_path,
                },
            )

    # -------------------------------------------------------------------------

    def _validate_behaviour_execution_settings(
        self,
        behaviour: dict[str, Any],
        behaviour_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate optional behaviour execution settings.
        """

        execution = behaviour.get("execution")

        if execution is None:
            execution = behaviour.get("runtime")

        if execution is None:
            return

        if not isinstance(execution, dict):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=("Behaviour execution settings must contain a JSON object."),
                details={
                    "actual_type": type(execution).__name__,
                },
            )

            return

        boolean_fields = (
            "enabled",
            "deterministic",
            "parallel",
            "retry_enabled",
            "retryEnabled",
        )

        for field_name in boolean_fields:
            if field_name in execution and not isinstance(execution[field_name], bool):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Execution field '{field_name}' must be Boolean."),
                    details={
                        "field": f"execution.{field_name}",
                        "actual_type": type(execution[field_name]).__name__,
                    },
                )

        non_negative_number_fields = (
            "timeout",
            "timeout_seconds",
            "timeoutSeconds",
            "retries",
            "retry_count",
            "retryCount",
            "priority",
        )

        for field_name in non_negative_number_fields:
            if field_name not in execution:
                continue

            value = execution[field_name]

            if isinstance(value, bool) or not isinstance(value, (int, float)):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Execution field '{field_name}' must be numeric."),
                    details={
                        "field": f"execution.{field_name}",
                        "actual_type": type(value).__name__,
                    },
                )

            elif value < 0:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Execution field '{field_name}' cannot be negative."),
                    details={
                        "field": f"execution.{field_name}",
                        "actual": value,
                    },
                )

        environment = execution.get("environment")

        if environment is not None and not isinstance(
            environment,
            (str, dict),
        ):
            self._add_asset_diagnostic(
                result=result,
                severity=ValidationSeverity.ERROR,
                code=ValidationCode.INVALID_BEHAVIOUR,
                path=behaviour_path,
                message=("Execution environment must be a string or object."),
                details={
                    "field": "execution.environment",
                    "actual_type": type(environment).__name__,
                },
            )

    # -------------------------------------------------------------------------

    def _validate_behaviour_dependencies(
        self,
        behaviour: dict[str, Any],
        behaviour_path: Path,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate optional behaviour dependency declarations.
        """

        dependency_value = None
        dependency_field = None

        for field_name in (
            "dependencies",
            "depends_on",
            "dependsOn",
            "requires",
            "asset_references",
            "assetReferences",
        ):
            if field_name in behaviour:
                dependency_field = field_name
                dependency_value = behaviour[field_name]
                break

        if dependency_field is None:
            return

        dependencies = self._extract_behaviour_dependencies(
            value=dependency_value,
            field_name=dependency_field,
            behaviour_path=behaviour_path,
            result=result,
        )

        known_asset_ids = self._get_scanned_asset_ids()
        seen_dependencies: set[str] = set()

        for dependency in dependencies:
            dependency_id = dependency.strip()

            if not dependency_id:
                continue

            if dependency_id in seen_dependencies:
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Behaviour dependency '{dependency_id}' is declared more than once."),
                    details={
                        "field": dependency_field,
                        "dependency": dependency_id,
                    },
                )

                continue

            seen_dependencies.add(dependency_id)

            if (
                self._looks_like_asset_id(dependency_id)
                and known_asset_ids
                and dependency_id not in known_asset_ids
            ):
                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(f"Behaviour references unknown asset '{dependency_id}'."),
                    details={
                        "field": dependency_field,
                        "dependency": dependency_id,
                    },
                )

    # -------------------------------------------------------------------------

    def _extract_behaviour_dependencies(
        self,
        value: Any,
        field_name: str,
        behaviour_path: Path,
        result: AssetValidationResult,
    ) -> list[str]:
        """
        Extract dependency identifiers from supported JSON structures.
        """

        dependencies: list[str] = []

        if value is None:
            return dependencies

        if isinstance(value, str):
            dependencies.append(value)
            return dependencies

        if isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str):
                    dependencies.append(item)
                    continue

                if isinstance(item, dict):
                    reference = self._reference_from_mapping(item)

                    if reference is not None:
                        dependencies.append(reference)
                    else:
                        self._add_asset_diagnostic(
                            result=result,
                            severity=ValidationSeverity.WARNING,
                            code=ValidationCode.INVALID_BEHAVIOUR,
                            path=behaviour_path,
                            message=(
                                f"Dependency entry "
                                f"'{field_name}[{index}]' does not "
                                f"declare an identifier."
                            ),
                            details={
                                "field": field_name,
                                "index": index,
                            },
                        )

                    continue

                self._add_asset_diagnostic(
                    result=result,
                    severity=ValidationSeverity.ERROR,
                    code=ValidationCode.INVALID_BEHAVIOUR,
                    path=behaviour_path,
                    message=(
                        f"Dependency entry '{field_name}[{index}]' must be a string or object."
                    ),
                    details={
                        "field": field_name,
                        "index": index,
                        "actual_type": type(item).__name__,
                    },
                )

            return dependencies

        if isinstance(value, dict):
            direct_reference = self._reference_from_mapping(value)

            if direct_reference is not None:
                dependencies.append(direct_reference)
                return dependencies

            for key, item in value.items():
                if isinstance(item, str):
                    dependencies.append(item)

                elif isinstance(item, list):
                    nested_dependencies = self._extract_behaviour_dependencies(
                        value=item,
                        field_name=f"{field_name}.{key}",
                        behaviour_path=behaviour_path,
                        result=result,
                    )

                    dependencies.extend(nested_dependencies)

                elif isinstance(item, dict):
                    reference = self._reference_from_mapping(item)

                    if reference is not None:
                        dependencies.append(reference)

                elif item is not None:
                    self._add_asset_diagnostic(
                        result=result,
                        severity=ValidationSeverity.ERROR,
                        code=ValidationCode.INVALID_BEHAVIOUR,
                        path=behaviour_path,
                        message=(f"Dependency value '{field_name}.{key}' has an unsupported type."),
                        details={
                            "field": f"{field_name}.{key}",
                            "actual_type": type(item).__name__,
                        },
                    )

            return dependencies

        self._add_asset_diagnostic(
            result=result,
            severity=ValidationSeverity.ERROR,
            code=ValidationCode.INVALID_BEHAVIOUR,
            path=behaviour_path,
            message=(f"Behaviour dependency field '{field_name}' has an unsupported type."),
            details={
                "field": field_name,
                "actual_type": type(value).__name__,
            },
        )

        return dependencies

    # -------------------------------------------------------------------------
    # Part 4B2 extension points
    # -------------------------------------------------------------------------

    def _validate_behaviour_prompts(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate behaviour prompt-package content.

        Replace this placeholder during Phase 12.1.1 Part 4B2.
        """

        raise NotImplementedError("Implemented in Phase 12.1.1 Part 4B2.")

    # -------------------------------------------------------------------------

    def _validate_behaviour_tests(
        self,
        asset,
        result: AssetValidationResult,
    ) -> None:
        """
        Validate behaviour test content.

        Replace this placeholder during Phase 12.1.1 Part 4B2.
        """

        raise NotImplementedError("Implemented in Phase 12.1.1 Part 4B2.")
