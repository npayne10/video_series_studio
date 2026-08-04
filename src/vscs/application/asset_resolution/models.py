"""Stable contracts for resolving production assets and canonical resources."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from vscs.domain.assets import AssetCategory, AssetStatus
from vscs.domain.caps import CAPStatus


class AssetResolutionStatus(StrEnum):
    """Overall result of one asset-resolution request."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    UNRESOLVED = "unresolved"


class AssetResolutionSeverity(StrEnum):
    """Severity assigned to a resolution diagnostic."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AssetResolutionRequest:
    """Request authoritative production data for one asset."""

    asset_id: str
    expected_category: AssetCategory | None = None
    require_approved_asset: bool = True
    require_cap: bool = True
    require_approved_cap: bool = True
    require_approved_references: bool = True

    def __post_init__(self) -> None:
        normalized = self.asset_id.strip().upper()
        if not normalized:
            raise ValueError("asset_id is required")
        object.__setattr__(self, "asset_id", normalized)


@dataclass(frozen=True, slots=True)
class AssetResolutionDiagnostic:
    """One traceable resolution finding."""

    code: str
    severity: AssetResolutionSeverity
    message: str
    subject: str = ""


@dataclass(frozen=True, slots=True)
class ResolvedAssetBinding:
    """Stable asset information safe to consume outside Asset Manager."""

    asset_id: str
    name: str
    category: AssetCategory
    description: str
    status: AssetStatus
    tags: tuple[str, ...]
    checksum: str


@dataclass(frozen=True, slots=True)
class ResolvedCAPBinding:
    """Canonical Asset Profile information linked to one asset."""

    asset_id: str
    title: str
    version: str
    status: CAPStatus
    canonical_description: str
    visual_identity: str
    production_notes: str
    checksum: str


@dataclass(frozen=True, slots=True)
class ResolvedReferenceBinding:
    """Approved canonical reference exposed through a stable string identity."""

    reference_id: str
    file_path: str
    reference_type: str
    role: str
    checksum: str


@dataclass(frozen=True, slots=True)
class AssetDependencyFingerprint:
    """Combined fingerprint used by incremental compilation."""

    asset_id: str
    asset_checksum: str
    cap_checksum: str = ""
    reference_checksums: tuple[str, ...] = ()

    @property
    def checksum(self) -> str:
        payload = {
            "asset_id": self.asset_id,
            "asset_checksum": self.asset_checksum,
            "cap_checksum": self.cap_checksum,
            "reference_checksums": list(self.reference_checksums),
        }
        return _checksum(payload)


@dataclass(frozen=True, slots=True)
class AssetResolutionResult:
    """Complete immutable outcome of one resolution request."""

    request: AssetResolutionRequest
    status: AssetResolutionStatus
    asset: ResolvedAssetBinding | None = None
    cap: ResolvedCAPBinding | None = None
    references: tuple[ResolvedReferenceBinding, ...] = ()
    diagnostics: tuple[AssetResolutionDiagnostic, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.status is AssetResolutionStatus.RESOLVED

    @property
    def fingerprint(self) -> AssetDependencyFingerprint | None:
        if self.asset is None:
            return None
        return AssetDependencyFingerprint(
            self.asset.asset_id,
            self.asset.checksum,
            self.cap.checksum if self.cap is not None else "",
            tuple(reference.checksum for reference in self.references),
        )


def stable_model_checksum(value: Any) -> str:
    """Return a deterministic checksum for a Pydantic or mapping-like model."""
    if hasattr(value, "model_dump"):
        raw = value.model_dump(mode="json")
    elif isinstance(value, dict):
        raw = value
    else:
        raise TypeError("value must support model_dump() or be a dictionary")
    return _checksum(raw)


def _checksum(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
