"""Behaviour asset validation mixin."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from .constants import (
    BEHAVIOUR_REQUIRED_DIRECTORIES,
    BEHAVIOUR_REQUIRED_FILES,
    DEFAULT_BEHAVIOUR,
    PROMPTS_FOLDER,
    TESTS_FOLDER,
)
from .models import AssetValidationResult, ValidationCode, ValidationSeverity
from .prompt_discovery import PromptPackage, PromptPackageDiscoverer

if TYPE_CHECKING:
    from .protocols import ValidatorProtocol

    _BehaviourMixinBase = ValidatorProtocol
else:

    class _BehaviourMixinBase:
        pass


class BehaviourValidationMixin(_BehaviourMixinBase):
    def _validate_behaviour_asset(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        self._validate_behaviour_required_structure(asset, result)
        self._validate_behaviour_definition(asset, result)
        self._validate_behaviour_prompts(asset, result)
        self._validate_behaviour_tests(asset, result)

    def _validate_behaviour_required_structure(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        root = Path(asset.path)
        for name in BEHAVIOUR_REQUIRED_DIRECTORIES:
            path = root / name
            if not path.is_dir():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.MISSING_DIRECTORY,
                    path,
                    f"Required behaviour directory '{name}' is missing or is not a directory.",
                    {"directory": name},
                )
        for name in BEHAVIOUR_REQUIRED_FILES:
            path = root / name
            if not path.is_file():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.MISSING_FILE,
                    path,
                    f"Required behaviour file '{name}' is missing or is not a file.",
                    {"required_file": name},
                )

    def _validate_behaviour_definition(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        path = Path(asset.path) / DEFAULT_BEHAVIOUR
        if not path.is_file():
            return
        behaviour = self._load_json_for_asset(
            path,
            result,
            ValidationCode.INVALID_BEHAVIOUR,
            "behaviour definition",
        )
        if behaviour is None:
            return
        if not isinstance(behaviour, dict) or not behaviour:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_BEHAVIOUR,
                path,
                "Behaviour definition must contain a non-empty JSON object.",
                {"actual_type": type(behaviour).__name__},
            )
            return
        self._validate_declared_asset_id(
            asset, result, behaviour, path, DEFAULT_BEHAVIOUR
        )
        self._validate_behaviour_identity(behaviour, path, result)
        self._validate_behaviour_version(behaviour, path, result)
        self._validate_behaviour_entry_point(
            behaviour, path, Path(asset.path), result
        )
        self._validate_behaviour_execution_settings(behaviour, path, result)
        self._validate_behaviour_dependencies(behaviour, path, result)
        result.metadata_count += 1
        self._record_file_hash(path, result, False)

    def _validate_behaviour_identity(
        self,
        behaviour: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        fields = (
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
        found = 0
        for field in fields:
            if field not in behaviour:
                continue
            found += 1
            value = behaviour[field]
            if not isinstance(value, str):
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    f"Behaviour field '{field}' must be a string.",
                    {"field": field, "actual_type": type(value).__name__},
                )
            elif not value.strip():
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.WARNING,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    f"Behaviour field '{field}' is empty.",
                    {"field": field},
                )
        if found == 0:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.INVALID_BEHAVIOUR,
                path,
                "Behaviour definition has no descriptive identity field.",
            )
        if "enabled" in behaviour and not isinstance(behaviour["enabled"], bool):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_BEHAVIOUR,
                path,
                "Behaviour field 'enabled' must be Boolean.",
            )

    def _validate_behaviour_version(
        self,
        behaviour: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        for field in (
            "version",
            "behaviour_version",
            "behaviourVersion",
            "schema_version",
            "schemaVersion",
        ):
            if field not in behaviour:
                continue
            value = behaviour[field]
            valid = (isinstance(value, str) and bool(value.strip())) or (
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
            )
            if not valid:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    (
                        f"Behaviour version field '{field}' must be a non-empty "
                        "string or non-negative integer."
                    ),
                    {"field": field, "actual": value},
                )

    def _validate_behaviour_entry_point(
        self,
        behaviour: dict[str, Any],
        behaviour_path: Path,
        asset_path: Path,
        result: AssetValidationResult,
    ) -> None:
        field = next(
            (
                name
                for name in (
                    "entry_point",
                    "entryPoint",
                    "handler",
                    "callable",
                    "module",
                    "script",
                )
                if name in behaviour
            ),
            None,
        )
        if field is None:
            return
        value = behaviour[field]
        if isinstance(value, str):
            value = value.strip()
            if not value:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_BEHAVIOUR,
                    behaviour_path,
                    f"Behaviour entry-point field '{field}' is empty.",
                )
                return
            if (
                "/" in value
                or "\\" in value
                or value.lower().endswith(
                    (".py", ".ps1", ".js", ".ts", ".bat", ".cmd")
                )
            ):
                self._validate_behaviour_relative_path(
                    value, behaviour_path, asset_path, result
                )
            elif ":" in value:
                module, callable_name = value.rsplit(":", 1)
                if not module.strip() or not callable_name.strip():
                    self._add_asset_diagnostic(
                        result,
                        ValidationSeverity.ERROR,
                        ValidationCode.INVALID_BEHAVIOUR,
                        behaviour_path,
                        "Behaviour module entry point must use 'module:callable'.",
                    )
            return
        if isinstance(value, dict):
            supported = {
                key: item
                for key, item in value.items()
                if key
                in {"module", "function", "callable", "handler", "path", "script"}
            }
            if not supported:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_BEHAVIOUR,
                    behaviour_path,
                    "Behaviour entry-point object contains no supported property.",
                )
                return
            for key, item in supported.items():
                if not isinstance(item, str) or not item.strip():
                    self._add_asset_diagnostic(
                        result,
                        ValidationSeverity.ERROR,
                        ValidationCode.INVALID_BEHAVIOUR,
                        behaviour_path,
                        (
                            f"Behaviour entry-point property '{key}' must be a "
                            "non-empty string."
                        ),
                    )
            declared_path = value.get("path") or value.get("script")
            if isinstance(declared_path, str) and declared_path.strip():
                self._validate_behaviour_relative_path(
                    declared_path.strip(), behaviour_path, asset_path, result
                )
            return
        self._add_asset_diagnostic(
            result,
            ValidationSeverity.ERROR,
            ValidationCode.INVALID_BEHAVIOUR,
            behaviour_path,
            f"Behaviour entry-point field '{field}' must be a string or object.",
        )

    def _validate_behaviour_relative_path(
        self,
        declared_path: str,
        behaviour_path: Path,
        asset_path: Path,
        result: AssetValidationResult,
    ) -> None:
        relative = Path(declared_path.replace("\\", "/"))
        if relative.is_absolute():
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_BEHAVIOUR,
                behaviour_path,
                "Behaviour entry point must not use an absolute path.",
                {"declared_path": declared_path},
            )
            return
        candidate = asset_path / relative
        try:
            candidate.resolve().relative_to(asset_path.resolve())
        except (OSError, ValueError):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_BEHAVIOUR,
                behaviour_path,
                "Behaviour entry-point path escapes the asset directory.",
                {"declared_path": declared_path},
            )
            return
        if not candidate.is_file():
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.MISSING_FILE,
                candidate,
                "Behaviour entry-point file does not currently exist.",
                {"declared_path": declared_path},
            )

    def _validate_behaviour_execution_settings(
        self,
        behaviour: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        execution = behaviour.get("execution", behaviour.get("runtime"))
        if execution is None:
            return
        if not isinstance(execution, dict):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.INVALID_BEHAVIOUR,
                path,
                "Behaviour execution settings must contain a JSON object.",
            )
            return
        for field in (
            "enabled",
            "deterministic",
            "parallel",
            "retry_enabled",
            "retryEnabled",
        ):
            if field in execution and not isinstance(execution[field], bool):
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    f"Execution field '{field}' must be Boolean.",
                )
        for field in (
            "timeout",
            "timeout_seconds",
            "timeoutSeconds",
            "retries",
            "retry_count",
            "retryCount",
            "priority",
        ):
            if field not in execution:
                continue
            value = execution[field]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.ERROR,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    f"Execution field '{field}' must be a non-negative number.",
                    {"actual": value},
                )

    def _validate_behaviour_dependencies(
        self,
        behaviour: dict[str, Any],
        path: Path,
        result: AssetValidationResult,
    ) -> None:
        field = next(
            (
                name
                for name in (
                    "dependencies",
                    "depends_on",
                    "dependsOn",
                    "requires",
                    "asset_references",
                    "assetReferences",
                )
                if name in behaviour
            ),
            None,
        )
        if field is None:
            return
        dependencies = self._extract_behaviour_dependencies(
            behaviour[field], field, path, result
        )
        known = self._get_scanned_asset_ids()
        seen: set[str] = set()
        for dependency in dependencies:
            dependency_id = dependency.strip()
            if not dependency_id:
                continue
            if dependency_id in seen:
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.WARNING,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    f"Behaviour dependency '{dependency_id}' is declared more than once.",
                )
                continue
            seen.add(dependency_id)
            if (
                self._looks_like_asset_id(dependency_id)
                and known
                and dependency_id not in known
            ):
                self._add_asset_diagnostic(
                    result,
                    ValidationSeverity.WARNING,
                    ValidationCode.INVALID_BEHAVIOUR,
                    path,
                    f"Behaviour references unknown asset '{dependency_id}'.",
                )

    def _extract_behaviour_dependencies(
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
            dependency_ids: list[str] = []
            for index, item in enumerate(value):
                if isinstance(item, str):
                    dependency_ids.append(item)
                elif isinstance(item, dict):
                    reference = self._reference_from_mapping(item)
                    if reference:
                        dependency_ids.append(reference)
                    else:
                        self._add_asset_diagnostic(
                            result,
                            ValidationSeverity.WARNING,
                            ValidationCode.INVALID_BEHAVIOUR,
                            path,
                            f"Dependency entry '{field}[{index}]' has no identifier.",
                        )
                else:
                    self._add_asset_diagnostic(
                        result,
                        ValidationSeverity.ERROR,
                        ValidationCode.INVALID_BEHAVIOUR,
                        path,
                        (
                            f"Dependency entry '{field}[{index}]' must be a string "
                            "or object."
                        ),
                    )
            return dependency_ids
        if isinstance(value, dict):
            direct = self._reference_from_mapping(value)
            if direct:
                return [direct]
            nested_dependency_ids: list[str] = []
            for key, item in value.items():
                nested_dependency_ids.extend(
                    self._extract_behaviour_dependencies(
                        item, f"{field}.{key}", path, result
                    )
                )
            return nested_dependency_ids
        self._add_asset_diagnostic(
            result,
            ValidationSeverity.ERROR,
            ValidationCode.INVALID_BEHAVIOUR,
            path,
            f"Behaviour dependency field '{field}' has an unsupported type.",
        )
        return []

    def _validate_behaviour_prompts(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        """Discover and structurally validate behaviour prompt packages."""
        directory = Path(asset.path) / PROMPTS_FOLDER
        if not directory.is_dir():
            return
        discovery = PromptPackageDiscoverer().discover(directory)
        result.prompt_packages.extend(discovery.packages)
        result.prompt_packages_valid += discovery.valid_package_count
        result.prompt_packages_ignored += len(discovery.ignored_entries)

        if not discovery.packages:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.EMPTY_DIRECTORY,
                directory,
                "Behaviour prompt directory contains no prompt packages.",
                {"ignored_entries": len(discovery.ignored_entries)},
            )
            return

        for package in discovery.packages:
            self._validate_prompt_package_structure(result, package)

    def _validate_prompt_package_structure(
        self, result: AssetValidationResult, package: PromptPackage
    ) -> None:
        self._add_asset_diagnostic(
            result,
            ValidationSeverity.INFO,
            ValidationCode.PROMPT_PACKAGE_DISCOVERED,
            package.path,
            f"Prompt package '{package.name}' discovered.",
            {"package": package.name},
        )
        for name in package.missing_directories:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.MISSING_DIRECTORY,
                package.path / name,
                f"Required prompt package directory '{name}' is missing.",
                {"package": package.name, "directory": name},
            )
        for name in package.empty_directories:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.EMPTY_DIRECTORY,
                package.path / name,
                f"Prompt package directory '{name}' is empty.",
                {"package": package.name, "directory": name},
            )
        for name in package.extra_directories:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.UNEXPECTED_DIRECTORY,
                package.path / name,
                f"Unexpected prompt package directory '{name}'.",
                {"package": package.name, "directory": name},
            )
        if not package.manifest_candidates:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.MISSING_FILE,
                package.path,
                "Prompt package manifest is missing.",
                {"package": package.name},
            )
        elif len(package.manifest_candidates) > 1:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.MULTIPLE_MANIFESTS,
                package.path,
                "Prompt package contains multiple recognised manifests.",
                {
                    "package": package.name,
                    "manifests": [path.name for path in package.manifest_candidates],
                },
            )
        if package.readme_path is None:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.MISSING_FILE,
                package.path / "README.md",
                "Prompt package README.md is missing.",
                {"package": package.name},
            )

    def _validate_behaviour_tests(
        self, asset: Any, result: AssetValidationResult
    ) -> None:
        """Part 4B2 extension point: validate behaviour test content."""
        directory = Path(asset.path) / TESTS_FOLDER
        if directory.is_dir() and not any(
            path.is_file() for path in directory.rglob("*")
        ):
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.WARNING,
                ValidationCode.EMPTY_DIRECTORY,
                directory,
                "Behaviour test directory is empty.",
            )
