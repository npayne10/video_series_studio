"""Validated construction boundary for Advanced Clip Production Packages."""

from __future__ import annotations

from .models import ClipProductionPackage
from .validator import ACPPValidationIssue, ACPPValidator


class ACPPBuildError(ValueError):
    """Raised when a clip package fails foundation validation."""

    def __init__(self, issues: tuple[ACPPValidationIssue, ...]) -> None:
        self.issues = issues
        summary = "; ".join(f"{issue.code}: {issue.message}" for issue in issues)
        super().__init__(summary or "ACPP package construction failed.")


class ClipProductionPackageBuilder:
    """Approve complete packages before persistence or downstream compilation."""

    def __init__(self, validator: ACPPValidator | None = None) -> None:
        self._validator = validator or ACPPValidator()

    def build(self, package: ClipProductionPackage) -> ClipProductionPackage:
        """Validate and return one immutable clip production package."""
        result = self._validator.validate(package)
        if not result.passed:
            raise ACPPBuildError(tuple(result.issues))
        return package
