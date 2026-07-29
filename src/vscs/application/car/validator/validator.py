"""CAR repository validator orchestration."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..scanner import AssetClass
from .base import ValidatorBase
from .behaviour import BehaviourValidationMixin
from .configuration import ConfigurationValidationMixin
from .constants import REPOSITORY_VERSION
from .health import HealthScoringMixin
from .models import (
    AssetValidationResult,
    RepositoryValidationResult,
    ValidationCode,
    ValidationDiagnostic,
    ValidationSeverity,
)
from .visual import VisualValidationMixin

LOGGER = logging.getLogger(__name__)


class CarRepositoryValidator(
    VisualValidationMixin,
    ConfigurationValidationMixin,
    BehaviourValidationMixin,
    HealthScoringMixin,
    ValidatorBase,
):
    """Read-only validator for Canonical Asset Repository v2."""

    def validate(self) -> RepositoryValidationResult:
        LOGGER.info("Starting CAR repository validation: %s", self.repository)
        self.scan_result = self.scanner.scan()
        self.result = RepositoryValidationResult(repository=self.scan_result.root)
        self.result.total_assets = len(self.scan_result.assets)

        self.validate_repository()

        for asset in self.scan_result.assets:
            asset_result = self.validate_asset(asset)
            self.result.assets.append(asset_result)
            if asset_result.passed:
                self.result.passed_assets += 1
            else:
                self.result.failed_assets += 1

        for diagnostic in self._all_diagnostics():
            if diagnostic.severity is ValidationSeverity.WARNING:
                self.result.warnings += 1
            elif diagnostic.severity is ValidationSeverity.ERROR:
                self.result.errors += 1
            elif diagnostic.severity is ValidationSeverity.CRITICAL:
                self.result.critical += 1

        self.result.repository_health = self.calculate_health()
        self.result.passed = self.result.critical == 0 and self.result.errors == 0
        LOGGER.info(
            "Repository validation complete (%s assets)",
            self.result.total_assets,
        )
        return self.result

    def _all_diagnostics(self) -> list[ValidationDiagnostic]:
        if self.result is None:
            return []
        diagnostics = list(self.result.diagnostics)
        for asset in self.result.assets:
            diagnostics.extend(asset.diagnostics)
        return diagnostics

    def validate_repository(self) -> None:
        if self.scan_result is None or self.result is None:
            raise RuntimeError("Repository has not been scanned.")

        if not self.repository.exists() or not self.repository.is_dir():
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.CRITICAL,
                    code=ValidationCode.INVALID_REPOSITORY,
                    asset_id=None,
                    path=self.repository,
                    message="Repository directory does not exist or is not a directory.",
                )
            )
            return

        versions = {
            asset.repository_version
            for asset in self.scan_result.assets
            if asset.repository_version
        }
        unexpected_versions = sorted(
            version for version in versions if version != REPOSITORY_VERSION
        )
        if unexpected_versions:
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=ValidationSeverity.WARNING,
                    code=ValidationCode.INVALID_REPOSITORY,
                    asset_id=None,
                    path=self.repository,
                    message=(
                        "One or more assets use repository versions that differ "
                        f"from expected version {REPOSITORY_VERSION}."
                    ),
                    details={
                        "expected": REPOSITORY_VERSION,
                        "actual": unexpected_versions,
                    },
                )
            )

        for issue in self.scan_result.issues:
            severity = (
                ValidationSeverity.ERROR
                if issue.severity.lower() == "error"
                else ValidationSeverity.WARNING
            )
            issue_path = self.repository / issue.path if issue.path else self.repository
            self.result.diagnostics.append(
                ValidationDiagnostic(
                    severity=severity,
                    code=ValidationCode.UNKNOWN,
                    asset_id=None,
                    path=issue_path,
                    message=issue.message,
                    details={"scanner_code": issue.code},
                )
            )

    def validate_asset(self, asset: Any) -> AssetValidationResult:
        if self.result is None:
            raise RuntimeError("Repository validation has not been initialised.")

        result = AssetValidationResult(
            asset_id=asset.asset_id,
            asset_class=asset.asset_class,
            asset_path=Path(asset.path),
        )

        if asset.asset_id in self._asset_ids:
            self.result.duplicate_asset_ids.add(asset.asset_id)
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.DUPLICATE_ASSET_ID,
                Path(asset.path),
                "Duplicate asset identifier.",
            )
        else:
            self._asset_ids.add(asset.asset_id)

        if not Path(asset.path).is_dir():
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.CRITICAL,
                ValidationCode.INVALID_REPOSITORY,
                Path(asset.path),
                "Asset directory does not exist.",
            )
            return result

        if asset.asset_class is AssetClass.VISUAL:
            self._validate_visual_asset(asset, result)
        elif asset.asset_class is AssetClass.CONFIGURATION:
            self._validate_configuration_asset(asset, result)
        elif asset.asset_class is AssetClass.BEHAVIOUR:
            self._validate_behaviour_asset(asset, result)
        else:
            self._add_asset_diagnostic(
                result,
                ValidationSeverity.ERROR,
                ValidationCode.UNKNOWN_ASSET_CLASS,
                Path(asset.path),
                "Unknown asset class.",
            )

        return result
