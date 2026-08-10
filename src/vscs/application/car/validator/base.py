"""Shared state and helper operations for CAR validation."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from ..scanner import CarRepositoryScanner, RepositoryScanResult
from .models import (
    AssetValidationResult,
    RepositoryValidationResult,
    ValidationCode,
    ValidationDiagnostic,
    ValidationSeverity,
)

LOGGER = logging.getLogger(__name__)


class ValidatorBase:
    def __init__(self, repository: Path | str) -> None:
        self.repository = Path(repository).expanduser().resolve()
        self.scanner = CarRepositoryScanner(self.repository)
        self.scan_result: RepositoryScanResult | None = None
        self.result: RepositoryValidationResult | None = None
        self._asset_ids: set[str] = set()
        self._file_hashes: dict[str, list[str]] = {}

    @staticmethod
    def calculate_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def load_json(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            LOGGER.exception("Unable to read JSON %s", path)
            return None
        return payload if isinstance(payload, dict) else None

    def _add_asset_diagnostic(
        self,
        result: AssetValidationResult,
        severity: ValidationSeverity,
        code: ValidationCode,
        path: Path | None,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        result.diagnostics.append(
            ValidationDiagnostic(
                severity=severity,
                code=code,
                asset_id=result.asset_id,
                path=path,
                message=message,
                details=details or {},
            )
        )
        if severity in {ValidationSeverity.ERROR, ValidationSeverity.CRITICAL}:
            result.passed = False

    def _load_json_for_asset(
        self,
        path: Path,
        result: AssetValidationResult,
        invalid_code: ValidationCode,
        description: str,
    ) -> Any | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                invalid_code,
                path,
                f"Invalid JSON in {description}.",
                {
                    "line": error.lineno,
                    "column": error.colno,
                    "position": error.pos,
                    "error": error.msg,
                },
            )
        except UnicodeDecodeError as error:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                invalid_code,
                path,
                f"{description.capitalize()} is not valid UTF-8.",
                {"error": str(error)},
            )
        except OSError as error:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                invalid_code,
                path,
                f"Unable to read {description}.",
                {"error": str(error)},
            )
        return None

    def _validate_declared_asset_id(
        self,
        asset: Any,
        result: AssetValidationResult,
        document: Any,
        document_path: Path,
        document_name: str,
    ) -> None:
        if not isinstance(document, dict):
            return
        for field_name in ("asset_id", "assetId", "id"):
            if field_name not in document:
                continue
            actual = str(document[field_name]).strip()
            expected = str(asset.asset_id).strip()
            if actual != expected:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_SCHEMA,
                    document_path,
                    f"Asset ID declared in {document_name} does not match the repository asset ID.",
                    {"field": field_name, "expected": expected, "actual": actual},
                )
            return

    def _record_file_hash(
        self,
        path: Path,
        result: AssetValidationResult,
        detect_duplicates: bool,
    ) -> str | None:
        try:
            file_hash = self.calculate_sha256(path)
        except OSError as error:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.UNKNOWN,
                path,
                "Unable to calculate file hash.",
                {"error": str(error)},
            )
            return None

        try:
            relative_path = str(path.relative_to(self.repository))
        except ValueError:
            relative_path = str(path)
        result.file_hashes[relative_path] = file_hash
        known_paths = self._file_hashes.setdefault(file_hash, [])

        if detect_duplicates and known_paths:
            duplicates = [*known_paths, relative_path]
            if self.result is not None:
                stored = self.result.duplicate_hashes.setdefault(file_hash, [])
                for duplicate in duplicates:
                    if duplicate not in stored:
                        stored.append(duplicate)
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.DUPLICATE_HASH,
                path,
                "Canonical image has the same content hash as another canonical image.",
                {"sha256": file_hash, "matching_files": duplicates},
            )

        if relative_path not in known_paths:
            known_paths.append(relative_path)
        return file_hash

    def _get_scanned_asset_ids(self) -> set[str]:
        if self.scan_result is None:
            return set()
        return {str(asset.asset_id).strip() for asset in self.scan_result.assets}

    @staticmethod
    def _looks_like_asset_id(value: str) -> bool:
        parts = value.strip().split("-")
        return (
            len(parts) >= 3
            and all(parts)
            and parts[0].isalpha()
            and any(character.isdigit() for character in parts[-1])
        )

    @staticmethod
    def _reference_from_mapping(value: dict[str, Any]) -> str | None:
        for field_name in ("asset_id", "assetId", "reference", "ref", "id"):
            candidate = value.get(field_name)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None
