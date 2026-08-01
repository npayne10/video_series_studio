"""Typing contracts shared by CAR validator mixins."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .models import AssetValidationResult, ValidationCode, ValidationSeverity


class ValidatorProtocol(Protocol):
    """Helper operations supplied by the concrete CAR validator."""

    def _add_asset_diagnostic(
        self,
        result: AssetValidationResult,
        severity: ValidationSeverity,
        code: ValidationCode,
        path: Path | None,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None: ...

    def _load_json_for_asset(
        self,
        path: Path,
        result: AssetValidationResult,
        invalid_code: ValidationCode,
        description: str,
    ) -> Any | None: ...

    def _validate_declared_asset_id(
        self,
        asset: Any,
        result: AssetValidationResult,
        document: Any,
        document_path: Path,
        document_name: str,
    ) -> None: ...

    def _record_file_hash(
        self,
        path: Path,
        result: AssetValidationResult,
        detect_duplicates: bool,
    ) -> str | None: ...

    def _get_scanned_asset_ids(self) -> set[str]: ...

    def _looks_like_asset_id(self, value: str) -> bool: ...

    def _reference_from_mapping(self, value: dict[str, Any]) -> str | None: ...
