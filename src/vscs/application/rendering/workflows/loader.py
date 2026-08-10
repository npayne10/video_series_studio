"""Workflow-manifest parsing and directory discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .manifest import WorkflowManifest
from .registry import DuplicateWorkflowManifestError, WorkflowRegistry


class ManifestDiagnosticLevel(StrEnum):
    """Severity of one manifest discovery finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ManifestDiagnostic:
    """One structured manifest loading or registration finding."""

    level: ManifestDiagnosticLevel
    path: Path
    message: str
    workflow_id: str | None = None


@dataclass(frozen=True, slots=True)
class ManifestDiscoveryResult:
    """Result of discovering and registering workflow manifests."""

    discovered_files: int
    loaded_workflow_ids: tuple[str, ...] = ()
    diagnostics: tuple[ManifestDiagnostic, ...] = ()

    @property
    def loaded_count(self) -> int:
        """Return the number of successfully registered manifests."""
        return len(self.loaded_workflow_ids)

    @property
    def error_count(self) -> int:
        """Return the number of error diagnostics."""
        return sum(item.level is ManifestDiagnosticLevel.ERROR for item in self.diagnostics)


class WorkflowManifestLoader:
    """Load validated JSON manifests without disrupting application startup."""

    SUPPORTED_MANIFEST_VERSIONS = frozenset({"1.0"})

    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve(strict=False)

    def parse_file(self, path: Path) -> WorkflowManifest:
        """Parse and validate one manifest file, raising on invalid input."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("workflow manifest root must be an object")
        manifest = WorkflowManifest.from_dict(raw)
        if manifest.metadata.manifest_version not in self.SUPPORTED_MANIFEST_VERSIONS:
            raise ValueError(f"unsupported manifest version: {manifest.metadata.manifest_version}")
        return manifest

    def discover(
        self,
        registry: WorkflowRegistry,
        *,
        replace: bool = False,
    ) -> ManifestDiscoveryResult:
        """Discover JSON manifests and register every valid document."""
        if not self.root.exists():
            return ManifestDiscoveryResult(
                discovered_files=0,
                diagnostics=(
                    ManifestDiagnostic(
                        ManifestDiagnosticLevel.INFO,
                        self.root,
                        "workflow manifest directory does not exist",
                    ),
                ),
            )
        if not self.root.is_dir():
            return ManifestDiscoveryResult(
                discovered_files=0,
                diagnostics=(
                    ManifestDiagnostic(
                        ManifestDiagnosticLevel.ERROR,
                        self.root,
                        "workflow manifest root is not a directory",
                    ),
                ),
            )

        files = tuple(sorted(self.root.rglob("*.json")))
        loaded: list[str] = []
        diagnostics: list[ManifestDiagnostic] = []
        for path in files:
            try:
                manifest = self.parse_file(path)
                registry.register(manifest, replace=replace)
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                diagnostics.append(
                    ManifestDiagnostic(
                        ManifestDiagnosticLevel.ERROR,
                        path,
                        str(exc),
                    )
                )
                continue
            except DuplicateWorkflowManifestError as exc:
                diagnostics.append(
                    ManifestDiagnostic(
                        ManifestDiagnosticLevel.WARNING,
                        path,
                        str(exc),
                    )
                )
                continue
            loaded.append(manifest.workflow_id)
            diagnostics.append(
                ManifestDiagnostic(
                    ManifestDiagnosticLevel.INFO,
                    path,
                    "workflow manifest loaded",
                    workflow_id=manifest.workflow_id,
                )
            )
        return ManifestDiscoveryResult(
            discovered_files=len(files),
            loaded_workflow_ids=tuple(loaded),
            diagnostics=tuple(diagnostics),
        )

    @staticmethod
    def write_manifest(path: Path, manifest: WorkflowManifest) -> None:
        """Write one manifest using stable, readable JSON formatting."""
        path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = manifest.to_dict()
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
