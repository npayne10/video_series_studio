from __future__ import annotations

import json
from pathlib import Path

from vscs.application.production_execution import CompiledProductionPackage
from vscs.application.rendering.workflows import WorkflowManifest
from vscs.infrastructure.production_execution import (
    LocalComfyUIProductionExecutionBackend,
    LTX23V721DeploymentAssurance,
)
from vscs.infrastructure.production_execution.ltx23_v721_backend import (
    LTX23_V721_PACKAGE_LOADER_CLASS,
    LTX23_V721_PACKAGE_LOADER_TITLE,
    LTX23_V721_REFERENCE_RESOLVER_CLASS,
    LTX23_V721_REFERENCE_RESOLVER_TITLE,
    LTX23_V721_WORKFLOW_FILE,
    LTX23_V721_WORKFLOW_ID,
    LocalLTX23V721ProductionPackageCompilationService,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = REPOSITORY_ROOT / "resources" / "workflows"


def _compiled(reference_plan: dict[str, object] | None = None) -> CompiledProductionPackage:
    return CompiledProductionPackage(
        task_id="PT-VIDEO-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-001",
        profile="production",
        authority_id="UPD-SHT-001",
        authority_revision=1,
        authority_fingerprint="authority-fingerprint",
        approved_by="human-reviewer",
        source_package_id="PP-SHT-001",
        source_package_fingerprint="source-package-fingerprint",
        source_schema_version="1.0",
        universal_text="Commander James Spence stands on the bridge under controlled light.",
        positive_prompt="Commander James Spence stands on the bridge under controlled light.",
        negative_prompt="identity drift, malformed anatomy",
        previous_approved_final_frame=None,
        filename_prefix="VSCS/Production/SHT-001",
        width=1280,
        height=720,
        frame_count=145,
        frames_per_second=24,
        cfg=1.25,
        ic_lora_strength=0.46,
        seed=56971365581327,
        composition_plan={"mode": "single_character"},
        production_authority={"approved": True},
        package_fingerprint="provider-neutral-fingerprint",
        reference_plan=reference_plan,
    )


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
    assert dict(manifest.extra)["governed_reference_resolution"] == "VSCSMultiReferenceResolverV721"
    assert dict(manifest.extra)["provider_visual_input_limit"] == "3"
    assert "governed_multi_reference" in manifest.capabilities


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


def test_v721_package_maps_governed_reference_authority_without_silent_weakening(
    tmp_path: Path,
) -> None:
    reference = tmp_path / "references" / "james-provider-ready.png"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"provider-ready-test-reference")
    plan = {
        "schema_version": "1.0",
        "status": "passed",
        "target": {"width": 1280, "height": 720},
        "references": [
            {
                "reference_id": "REF-JAMES-001",
                "role": "primary_identity",
                "reference_class": "provider_ready_derivative",
                "priority": "required",
                "subject_type": "character",
                "source_path": str(reference.relative_to(tmp_path)),
                "canonical_source_id": "CAP-JAMES-001",
                "asset_id": "CHR-JAMES",
                "label": "Commander James Spence 16:9 provider-ready identity",
                "width": 1280,
                "height": 720,
                "provider_ready": True,
                "provider_profiles": ["production-video-16x9"],
                "coverage": {
                    "framing_type": "full_body",
                    "coverage": "full_required_asset",
                    "required_features_visible": True,
                    "identity_visible": True,
                    "full_required_asset_visible": True,
                },
                "file_checksum": "checksum",
                "reference_fingerprint": "reference-fingerprint",
            }
        ],
        "diagnostics": [],
    }
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    payload = service._comfyui_payload(_compiled(plan))

    assert payload["schema_version"] == "7.2.1-vscs-1"
    assert payload["status"] == "READY"
    assert payload["acpp"]["prompts"]["positive"] == payload["shot_prompt"]
    assert payload["acpp"]["generation"]["width"] == 1280
    assert payload["acpp"]["generation"]["height"] == 720
    assert payload["acpp"]["generation"]["cfg"] == 1.25
    assert payload["acpp"]["generation"]["ic_lora_model_strength"] == 0.46
    binding = payload["reference_plan"]["bindings"][0]
    assert Path(binding["path"]) == reference.resolve(strict=False)
    assert binding["required"] is True
    assert binding["provider_ready"] is True
    assert binding["role"] == "primary_identity"
    assert binding["coverage"] == ["required_features", "full_required_asset", "identity"]
    assert binding["required_coverage"] == [
        "required_features",
        "full_required_asset",
        "identity",
    ]
    assert payload["reference_plan"]["references"][0]["source_path"] == str(
        reference.relative_to(tmp_path)
    )
    manifest = payload["_vscs_manifest"]
    content = dict(payload)
    content.pop("_vscs_manifest")
    assert manifest["package_fingerprint"] == service._fingerprint(content)


def test_v721_binding_preserves_explicit_start_frame_role(tmp_path: Path) -> None:
    reference = tmp_path / "continuity" / "previous-final-frame.png"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"continuity-frame")
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    binding = service._provider_reference_binding(
        {
            "reference_id": "REF-START-001",
            "role": "start_frame_reference",
            "reference_class": "continuity_capture",
            "priority": "required",
            "source_path": str(reference.relative_to(tmp_path)),
            "provider_ready": True,
            "coverage": {
                "required_features_visible": True,
                "identity_visible": True,
                "full_required_asset_visible": True,
            },
        }
    )

    assert binding["role"] == "start_frame_reference"
    assert binding["required"] is True
    assert Path(binding["path"]) == reference.resolve(strict=False)


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


def test_deployment_assurance_rejects_broken_multi_reference_guide_chain(tmp_path: Path) -> None:
    workflow_root = tmp_path / "resources" / "workflows"
    workflow_path = workflow_root / LTX23_V721_WORKFLOW_FILE
    workflow_path.parent.mkdir(parents=True)
    raw = json.loads((WORKFLOW_ROOT / LTX23_V721_WORKFLOW_FILE).read_text(encoding="utf-8"))
    raw["109"]["inputs"]["latent"] = ["103", 0]
    workflow_path.write_text(json.dumps(raw), encoding="utf-8")

    issues = LTX23V721DeploymentAssurance(workflow_root).inspect()

    assert any("latent chain is broken" in issue for issue in issues)
