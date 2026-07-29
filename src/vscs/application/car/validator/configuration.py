"""Configuration asset validation mixin."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import (
    CONFIGURATION_REQUIRED_FILES,
    DEFAULT_DESCRIPTION,
    DEFAULT_PROFILE,
)
from .models import AssetValidationResult, ValidationCode, ValidationSeverity


class ConfigurationValidationMixin:
    def _validate_configuration_asset(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        self._validate_configuration_required_files(asset, result)
        self._validate_configuration_profile(asset, result)
        self._validate_configuration_description(asset, result)

    def _validate_configuration_required_files(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        for name in CONFIGURATION_REQUIRED_FILES:
            path = Path(asset.path) / name
            if not path.is_file():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.MISSING_FILE,
                    path,
                    f"Required configuration file '{name}' is missing or is not a file.",
                    {"required_file": name},
                )

    def _validate_configuration_profile(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        path = Path(asset.path) / DEFAULT_PROFILE
        if not path.is_file():
            return
        profile = self._load_json_for_asset(
            path, result, ValidationCode.INVALID_PROFILE, "configuration profile"
        )
        if profile is None:
            return
        if not isinstance(profile, dict):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_PROFILE,
                path,
                "Configuration profile must contain a JSON object at its root.",
                {"actual_type": type(profile).__name__},
            )
            return
        if not profile:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.INVALID_PROFILE,
                path,
                "Configuration profile is an empty JSON object.",
            )
        self._validate_declared_asset_id(asset, result, profile, path, DEFAULT_PROFILE)
        self._validate_configuration_identity_fields(profile, path, result)
        self._validate_configuration_version(profile, path, result)
        self._validate_configuration_references(profile, path, result)
        self._validate_configuration_values(profile, "$", path, result)
        result.metadata_count += 1
        self._record_file_hash(path, result, False)

    def _validate_configuration_identity_fields(
        self,
        profile: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        for field in (
            "name", "title", "display_name", "displayName", "category",
            "type", "profile_type", "profileType",
        ):
            if field not in profile:
                continue
            value = profile[field]
            if not isinstance(value, str):
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_PROFILE,
                    path,
                    f"Configuration profile field '{field}' must be a string.",
                    {"field": field, "actual_type": type(value).__name__},
                )
            elif not value.strip():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.WARNING,
                    ValidationCode.INVALID_PROFILE,
                    path,
                    f"Configuration profile field '{field}' is empty.",
                    {"field": field},
                )

    def _validate_configuration_version(
        self,
        profile: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        for field in (
            "version", "profile_version", "profileVersion",
            "schema_version", "schemaVersion",
        ):
            if field not in profile:
                continue
            value = profile[field]
            valid = (
                isinstance(value, str) and bool(value.strip())
            ) or (
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
            )
            if not valid:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_PROFILE,
                    path,
                    f"Configuration version field '{field}' must be a non-empty string or non-negative integer.",
                    {"field": field, "actual": value},
                )

    def _validate_configuration_references(
        self,
        profile: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        known = self._get_scanned_asset_ids()
        for field in (
            "asset_reference", "assetReference", "asset_references",
            "assetReferences", "references", "depends_on", "dependsOn",
            "dependencies",
        ):
            if field not in profile:
                continue
            for reference in self._extract_reference_values(
                profile[field], field, path, result
            ):
                reference_id = reference.strip()
                if (
                    reference_id
                    and self._looks_like_asset_id(reference_id)
                    and known
                    and reference_id not in known
                ):
                    self._add_asset_diagnostic(
                        result,
                        ValidationSeverity.WARNING,
                        ValidationCode.INVALID_PROFILE,
                        path,
                        f"Configuration profile references unknown asset '{reference_id}'.",
                        {"field": field, "reference": reference_id},
                    )

    def _extract_reference_values(
        self,
        value: Any,
        field: str,
        path: Path,
        result: AssetValidationResult,
    ) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            references: list[str] = []
            for index, item in enumerate(value):
                if isinstance(item, str):
                    references.append(item)
                elif isinstance(item, dict):
                    reference = self._reference_from_mapping(item)
                    if reference:
                        references.append(reference)
                    else:
                        self._add_asset_diagnostic(
                            result,
                            ValidationSeverity.WARNING,
                            ValidationCode.INVALID_PROFILE,
                            path,
                            f"Reference entry '{field}[{index}]' does not declare an asset ID.",
                        )
                else:
                    self._add_asset_diagnostic(
                        result,
                        ValidationSeverity.ERROR,
                        ValidationCode.INVALID_PROFILE,
                        path,
                        f"Reference entry '{field}[{index}]' must be a string or object.",
                        {"actual_type": type(item).__name__},
                    )
            return references
        if isinstance(value, dict):
            direct = self._reference_from_mapping(value)
            if direct:
                return [direct]
            references: list[str] = []
            for key, item in value.items():
                references.extend(
                    self._extract_reference_values(
                        item, f"{field}.{key}", path, result
                    )
                )
            return references
        self._add_asset_diagnostic(
            result,
            ValidationSeverity.ERROR,
            ValidationCode.INVALID_PROFILE,
            path,
            f"Configuration reference field '{field}' has an unsupported type.",
            {"actual_type": type(value).__name__},
        )
        return []

    def _validate_configuration_values(
        self,
        value: Any,
        value_path: str,
        path: Path,
        result: AssetValidationResult,
        depth: int = 0,
    ) -> None:
        if depth > 32:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_PROFILE,
                path,
                "Configuration profile exceeds the maximum supported nesting depth.",
                {"json_path": value_path, "maximum_depth": 32},
            )
            return
        if isinstance(value, dict):
            for key, child in value.items():
                self._validate_configuration_values(
                    child, f"{value_path}.{key}", path, result, depth + 1
                )
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self._validate_configuration_values(
                    child, f"{value_path}[{index}]", path, result, depth + 1
                )
        elif isinstance(value, float) and (
            value != value or value in (float("inf"), float("-inf"))
        ):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_PROFILE,
                path,
                "Configuration profile contains a non-finite numeric value.",
                {"json_path": value_path, "actual": str(value)},
            )

    def _validate_configuration_description(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        path = Path(asset.path) / DEFAULT_DESCRIPTION
        if not path.is_file():
            return
        try:
            description = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_SCHEMA,
                path,
                "Unable to read configuration description as UTF-8.",
                {"error": str(error)},
            )
            return
        stripped = description.strip()
        if not stripped:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.EMPTY_DIRECTORY,
                path,
                "Configuration description is empty.",
            )
        elif len(stripped) < 20:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.INVALID_SCHEMA,
                path,
                "Configuration description is unusually short.",
                {"character_count": len(stripped), "recommended_minimum": 20},
            )
        if "\x00" in description:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_SCHEMA,
                path,
                "Configuration description contains null characters.",
            )
        self._record_file_hash(path, result, False)
