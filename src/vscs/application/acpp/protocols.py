"""Typing contracts for Advanced Clip Production Package services."""

from __future__ import annotations

from typing import Protocol

from .models import ClipProductionPackage


class ClipPackageValidator(Protocol):
    """Validate a complete clip production package."""

    def validate(self, package: ClipProductionPackage) -> object:
        """Return a validation result for one package."""
        ...


class ClipPackageSerializer(Protocol):
    """Serialize and restore clip production packages."""

    def dumps(self, package: ClipProductionPackage) -> str:
        """Serialize one package to JSON text."""
        ...

    def loads(self, payload: str) -> ClipProductionPackage:
        """Restore one package from JSON text."""
        ...
