from __future__ import annotations

import json
from pathlib import Path

from vscs.application.rendering.workflows import WorkflowManifest
from vscs.infrastructure.production_execution import (
    LTX23V721DeploymentAssurance,
    LocalComfyUIProductionExecutionBackend,
)
from vscs.infrastructure.production_execution.ltx23_v721_backend import (
    LTX23_V721_PACKAGE_LOADER_CLASS,
    LTX23_V721_PACKAGE_LOADER_TITLE,
    LTX23_V721_REFERENCE_RESOLVER_CLASS,
    LTX23_V721_REFERENCE_RESOLVER_TITLE,
    LTX23_V721_WORKFLOW_FILE,
    LTX23_V721_WORKFLOW_ID,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = REPOSITORY_ROOT / "resources" / "workflows"


def test_checked_in_ltx23_v721_workflow_passes_deployment_assurance() -> None:
    assert LTX23V721DeploymentAssurance(WORKFLOW_ROOT).inspect() == ()


def test_ltx23_production_manifest_is_package_driven_and_parseable() -> None:
    manifest_path = WORKFLOW_ROOT / "manifests" / "ltx23_production_v1.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest = WorkflowManifest.from_dict(raw)

    assert manifest.metadata.workflow_id == LTX23_V721_WORKFLOW_ID
    assert manifest.workflow_file == LTX23_V721_WORKFLOW_FILE
    assert manifest.bindings == ()
    assert dict(manifest.extra)["binding_mode"] == "production_package_v7_2_1"


def test_exported_production_backend_builds_v721_package_adapter(tmp_path: Path) -> None:
    backend = LocalComfyUIProductionExecutionBackend(
        tmp_path,
        endpoint="http://127.0.0.1:8188",
        comfyui_output_directory=None,
    )

    adapter = backend._workflow_foundation()
    manifest = adapter.registry.require(LTX23_V721_WORKFLOW_ID)
    workflow = adapter.compiler.load_workflow(manifest)

    loader = workflow["107"]
    resolver = workflow["108"]
    assert adapter.production_package_class_type == LTX23_V721_PACKAGE_LOADER_CLASS
    assert adapter.production_package_title == LTX23_V721_PACKAGE_LOADER_TITLE
    assert loader["class_type"] == LTX23_V721_PACKAGE_LOADER_CLASS
    assert loader["_meta"]["title"] == LTX23_V721_PACKAGE_LOADER_TITLE
    assert loader["inputs"]["production_package"] == ""
    assert resolver["class_type"] == LTX23_V721_REFERENCE_RESOLVER_CLASS
    assert resolver["_meta"]["title"] == LTX23_V721_REFERENCE_RESOLVER_TITLE


def test_deployment_assurance_rejects_hardcoded_package_path(tmp_path: Path) -> None:
    workflow_root = tmp_path / "resources" / "workflows"
    workflow_path = workflow_root / LTX23_V721_WORKFLOW_FILE
    workflow_path.parent.mkdir(parents=True)
    raw = json.loads((WORKFLOW_ROOT / LTX23_V721_WORKFLOW_FILE).read_text(encoding="utf-8"))
    raw["107"]["inputs"]["production_package"] = "D:/machine-specific/package.json"
    workflow_path.write_text(json.dumps(raw), encoding="utf-8")

    issues = LTX23V721DeploymentAssurance(workflow_root).inspect()

    assert any("production package path must remain blank" in issue for issue in issues)


def test_deployment_assurance_rejects_missing_governed_reference_resolver(tmp_path: Path) -> None:
    workflow_root = tmp_path / "resources" / "workflows"
    workflow_path = workflow_root / LTX23_V721_WORKFLOW_FILE
    workflow_path.parent.mkdir(parents=True)
    raw = json.loads((WORKFLOW_ROOT / LTX23_V721_WORKFLOW_FILE).read_text(encoding="utf-8"))
    raw.pop("108")
    workflow_path.write_text(json.dumps(raw), encoding="utf-8")

    issues = LTX23V721DeploymentAssurance(workflow_root).inspect()

    assert any("governed reference resolver" in issue for issue in issues)
