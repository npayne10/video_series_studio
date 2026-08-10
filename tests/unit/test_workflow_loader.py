"""Tests for workflow manifest loading and directory discovery."""

from __future__ import annotations

import json
from pathlib import Path

from vscs.application.rendering import (
    ManifestDiagnosticLevel,
    QualityLevel,
    RendererKind,
    WorkflowManifest,
    WorkflowManifestLoader,
    WorkflowMetadata,
    WorkflowRegistry,
)


def _manifest(workflow_id: str = "ltx-preview") -> WorkflowManifest:
    return WorkflowManifest(
        metadata=WorkflowMetadata(
            workflow_id=workflow_id,
            display_name="LTX Preview",
            description="Preview workflow",
            renderer=RendererKind.COMFYUI,
            workflow_version="1.0",
        ),
        quality_levels=(QualityLevel.PREVIEW,),
        workflow_file="workflows/ltx_preview_api.json",
    )


def test_loader_writes_and_parses_manifest(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    manifest = _manifest()
    WorkflowManifestLoader.write_manifest(path, manifest)

    loaded = WorkflowManifestLoader(tmp_path).parse_file(path)

    assert loaded == manifest
    assert (
        json.loads(path.read_text(encoding="utf-8"))["metadata"]["workflow_id"]
        == manifest.workflow_id
    )


def test_discovery_loads_valid_files_and_reports_invalid_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "manifests"
    WorkflowManifestLoader.write_manifest(root / "valid.json", _manifest())
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "broken.json").write_text("{broken", encoding="utf-8")

    registry = WorkflowRegistry()
    result = WorkflowManifestLoader(root).discover(registry)

    assert result.discovered_files == 2
    assert result.loaded_workflow_ids == ("ltx-preview",)
    assert result.loaded_count == 1
    assert result.error_count == 1
    assert registry.require("ltx-preview").workflow_id == "ltx-preview"


def test_discovery_handles_duplicates_and_missing_root(tmp_path: Path) -> None:
    root = tmp_path / "manifests"
    WorkflowManifestLoader.write_manifest(root / "one.json", _manifest())
    WorkflowManifestLoader.write_manifest(root / "two.json", _manifest())

    result = WorkflowManifestLoader(root).discover(WorkflowRegistry())

    assert result.loaded_count == 1
    assert any(item.level is ManifestDiagnosticLevel.WARNING for item in result.diagnostics)

    missing = WorkflowManifestLoader(tmp_path / "missing").discover(WorkflowRegistry())
    assert missing.discovered_files == 0
    assert missing.error_count == 0


def test_loader_rejects_unsupported_manifest_version(tmp_path: Path) -> None:
    path = tmp_path / "future.json"
    raw = _manifest().to_dict()
    raw["metadata"]["manifest_version"] = "2.0"
    path.write_text(json.dumps(raw), encoding="utf-8")

    result = WorkflowManifestLoader(tmp_path).discover(WorkflowRegistry())

    assert result.loaded_count == 0
    assert result.error_count == 1
    assert "unsupported manifest version" in result.diagnostics[0].message
