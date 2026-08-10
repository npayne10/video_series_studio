"""Visual asset validation mixin."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .constants import (
    CANON_FOLDER,
    DEFAULT_MANIFEST,
    METADATA_FOLDER,
    PROMPTS_FOLDER,
    SUPPORTED_IMAGE_EXTENSIONS,
    VISUAL_METADATA_FILES,
    VISUAL_REQUIRED_DIRECTORIES,
)
from .models import AssetValidationResult, ValidationCode, ValidationSeverity

if TYPE_CHECKING:
    from .protocols import ValidatorProtocol

    _VisualMixinBase = ValidatorProtocol
else:

    class _VisualMixinBase:
        pass


class VisualValidationMixin(_VisualMixinBase):
    def _validate_visual_asset(self, asset: Any, result: AssetValidationResult) -> None:
        self._validate_visual_directories(asset, result)
        self._validate_visual_manifest(asset, result)
        self._validate_visual_metadata(asset, result)
        self._validate_canonical_images(asset, result)
        self._validate_visual_prompts(asset, result)

    def _validate_visual_directories(self, asset: Any, result: AssetValidationResult) -> None:
        for name in VISUAL_REQUIRED_DIRECTORIES:
            path = Path(asset.path) / name
            if not path.exists() or not path.is_dir():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.MISSING_DIRECTORY,
                    path,
                    f"Required visual asset directory '{name}' is missing or is not a directory.",
                    {"directory": name},
                )

    def _validate_visual_manifest(self, asset: Any, result: AssetValidationResult) -> None:
        path = Path(asset.path) / DEFAULT_MANIFEST
        if not path.is_file():
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.MISSING_FILE,
                path,
                "Visual asset manifest.json is missing.",
            )
            return
        payload = self._load_json_for_asset(
            path, result, ValidationCode.INVALID_MANIFEST, "visual asset manifest"
        )
        if payload is None:
            return
        if not isinstance(payload, dict):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_MANIFEST,
                path,
                "Visual asset manifest must contain a JSON object.",
                {"actual_type": type(payload).__name__},
            )
            return
        self._validate_declared_asset_id(asset, result, payload, path, DEFAULT_MANIFEST)
        self._record_file_hash(path, result, False)

    def _validate_visual_metadata(self, asset: Any, result: AssetValidationResult) -> None:
        directory = Path(asset.path) / METADATA_FOLDER
        if not directory.is_dir():
            return
        for name in VISUAL_METADATA_FILES:
            path = directory / name
            if not path.is_file():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.MISSING_METADATA,
                    path,
                    f"Required visual metadata file '{name}' is missing.",
                )
                continue
            payload = self._load_json_for_asset(
                path, result, ValidationCode.INVALID_SCHEMA, f"metadata file '{name}'"
            )
            if payload is None:
                continue
            if not isinstance(payload, dict):
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_SCHEMA,
                    path,
                    f"Metadata file '{name}' must contain a JSON object.",
                )
                continue
            result.metadata_count += 1
            self._validate_declared_asset_id(asset, result, payload, path, name)
            self._record_file_hash(path, result, False)

    def _validate_canonical_images(self, asset: Any, result: AssetValidationResult) -> None:
        directory = Path(asset.path) / CANON_FOLDER
        if not directory.is_dir():
            return
        images = sorted(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
        )
        result.image_count = len(images)
        if not images:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.MISSING_CANONICAL_IMAGE,
                directory,
                "Visual asset does not contain a supported canonical image.",
                {"supported_extensions": sorted(SUPPORTED_IMAGE_EXTENSIONS)},
            )
            return
        for path in images:
            try:
                if path.stat().st_size == 0:
                    raise OSError("file is empty")
            except OSError as error:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.MISSING_CANONICAL_IMAGE,
                    path,
                    "Canonical image could not be inspected or is empty.",
                    {"error": str(error)},
                )
                continue
            self._record_file_hash(path, result, True)

    def _validate_visual_prompts(self, asset: Any, result: AssetValidationResult) -> None:
        directory = Path(asset.path) / PROMPTS_FOLDER
        if not directory.is_dir():
            return
        files = sorted(path for path in directory.rglob("*") if path.is_file())
        result.prompt_count = len(files)
        if not files:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.EMPTY_DIRECTORY,
                directory,
                "Visual asset prompt directory is empty.",
            )
            return
        for path in files:
            try:
                if path.stat().st_size == 0:
                    self._add_asset_diagnostic(
                        result,
                        ValidationSeverity.WARNING,
                        ValidationCode.EMPTY_DIRECTORY,
                        path,
                        "Visual asset prompt file is empty.",
                    )
            except OSError as error:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.WARNING,
                    ValidationCode.UNUSED_FILE,
                    path,
                    "Prompt file could not be inspected.",
                    {"error": str(error)},
                )
                continue
            if path.suffix.lower() == ".json":
                payload = self._load_json_for_asset(
                    path, result, ValidationCode.INVALID_JSON, "visual prompt JSON"
                )
                if payload is not None:
                    self._validate_declared_asset_id(asset, result, payload, path, path.name)
            self._record_file_hash(path, result, False)
