"""C4B.2A test fixtures are disposable; never touch the Diagnostic Console."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from vscs.application.caps.c4b2_disposable_runtime import (
    C4B2IsolationError,
    audit_c4b2_external_result,
    inspect_c4b2_offline_runtime_schemas,
    prepare_c4b2_disposable_bundle,
    preview_c4b2_isolated_launch,
    verify_c4b2_disposable_bundle,
)
from vscs.application.caps.general_visual_correction_triage import candidate_visual_triage
from vscs.application.caps.geometry_correction_policy import GeometryDefect
from vscs.application.caps.governed_visual_correction_handoff import (
    prepare_governed_correction_proposal,
)
from vscs.application.caps.human_reviewed_mask_evidence import (
    prepare_reviewed_mask,
    save_reviewed_mask_once,
)
from vscs.application.caps.spatial_visual_evidence import (
    NormalizedRegion,
    VisualEvidenceStatus,
    propose_spatial_evidence,
)
from vscs.application.caps.visual_candidate_quality import CandidateQualityResult


def _fixture(tmp_path: Path):
    protected = tmp_path / "protected_production_project"
    protected.mkdir()
    project = tmp_path / "only_disposable_test_project"
    project.mkdir()
    (project / ".c4b2_disposable_project").write_text(
        "C4B2_DISPOSABLE_PROJECT\n", encoding="utf-8"
    )
    image_folder = project / "Canonical Assets" / "STORY-C4B2-SYNTHETIC" / "Images"
    image_folder.mkdir(parents=True)
    source = image_folder / "source.png"
    Image.new("RGB", (320, 256), (20, 40, 60)).save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    snapshot = SimpleNamespace(
        project_root=project,
        image_path=source,
        asset_id="STORY-C4B2-SYNTHETIC",
        reference_id=8,
        image_sha256=digest,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "Three buttons and a recessed dial"),
            ("geometry", "A separate upright workstation"),
        ),
    )
    report = CandidateQualityResult(
        snapshot=snapshot,
        technical=SimpleNamespace(decision=SimpleNamespace(value="review")),
        semantic=None,
        recommendations=(),
    )
    triage = candidate_visual_triage(report)
    review = propose_spatial_evidence(
        triage,
        field="components",
        status=VisualEvidenceStatus.FAILED,
        observation="The dial protrudes instead of being recessed",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=NormalizedRegion(0.2, 0.2, 0.2, 0.3),
    )
    review = propose_spatial_evidence(
        triage,
        previous=review,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="Workstation is separate",
    )
    proposal = prepare_governed_correction_proposal(
        review,
        target_field="components",
        expected_source_sha256=digest,
        reviewer_confirmed_roi=True,
    )
    mask_dir = project / "Canonical Assets" / snapshot.asset_id / ".metadata" / "spatial_masks"
    mask_dir.mkdir(parents=True)
    evidence = prepare_reviewed_mask(
        proposal, source_path=source, reviewer_confirmed_mask=True
    )
    mask = save_reviewed_mask_once(
        evidence,
        proposal=proposal,
        source_path=source,
        destination_directory=mask_dir,
    )
    return snapshot, proposal, mask, protected


def _prepared(tmp_path: Path):
    snapshot, proposal, mask, protected = _fixture(tmp_path)
    path = tmp_path / "c4b2_external_bundle"
    prepared = prepare_c4b2_disposable_bundle(
        snapshot,
        proposal,
        selected_mask_path=mask,
        protected_project_root=protected,
        bundle_directory=path,
        seed=43,
    )
    return snapshot, proposal, mask, protected, prepared


def test_c4b2_disposable_staging_is_sealed_and_has_no_execution(tmp_path):
    snap, proposal, mask, protected, prepared = _prepared(tmp_path)
    assert prepared.directory == tmp_path / "c4b2_external_bundle"
    assert prepared.source_sha256 == snap.image_sha256
    assert prepared.mask_sha256 == hashlib.sha256(mask.read_bytes()).hexdigest()
    assert len(prepared.manifest_sha256) == 64
    assert prepared.dimensions == (320, 256)
    assert prepared.dedicated_port == 8298
    assert not prepared.execution_authorized
    assert not prepared.attempt_reservation_allowed
    assert not prepared.candidate_registration_allowed
    assert verify_c4b2_disposable_bundle(prepared.directory) == prepared
    assert sorted(folder.name for folder in prepared.directory.iterdir()) == sorted(
        ["input", "output", "temp", "user", "c4b2_manifest.json", "c4b2_api_graph.json"]
    )
    data = json.loads((prepared.directory / "c4b2_manifest.json").read_text())
    graph = json.loads((prepared.directory / "c4b2_api_graph.json").read_text())
    assert data["execution_authorized"] is False
    assert data["source_sha256"] == snap.image_sha256
    assert data["c1_proposal_sha256"] == proposal.proposal_sha256
    assert "XCIC" not in str(graph)
    assert graph["C4B_SOURCE"]["inputs"]["image"] == data["source_filename"]
    assert graph["C4B_MASK"]["inputs"]["image"] == data["mask_filename"]
    assert graph["9"]["inputs"]["filename_prefix"] == "C4B_DISPOSABLE_QUALIFICATION"
    assert not list(prepared.directory.joinpath("output").iterdir())
    assert not list(protected.iterdir())
    with pytest.raises(C4B2IsolationError, match="target must be new"):
        prepare_c4b2_disposable_bundle(
            snap,
            proposal,
            selected_mask_path=mask,
            protected_project_root=protected,
            bundle_directory=prepared.directory,
        )


def test_c4b2_rejects_missing_marker_and_workspace_collisions(tmp_path):
    snap, proposal, mask, protected = _fixture(tmp_path)
    marker = snap.project_root / ".c4b2_disposable_project"
    marker.unlink()
    with pytest.raises(C4B2IsolationError, match="marker"):
        prepare_c4b2_disposable_bundle(
            snap, proposal, selected_mask_path=mask,
            protected_project_root=protected, bundle_directory=tmp_path / "outside",
        )
    marker.write_text("C4B2_DISPOSABLE_PROJECT\n")
    for target in (snap.project_root / "bundle", protected / "bundle", tmp_path / "protected_production_project"):
        with pytest.raises(C4B2IsolationError):
            prepare_c4b2_disposable_bundle(
                snap, proposal, selected_mask_path=mask,
                protected_project_root=protected, bundle_directory=target,
            )


def test_c4b2_rejects_protected_identity_even_with_marker(tmp_path):
    snap, proposal, mask, protected = _fixture(tmp_path)
    snap.asset_id = "STORY-PRO-B00D168E43"
    with pytest.raises(C4B2IsolationError, match="protected Diagnostic Console"):
        prepare_c4b2_disposable_bundle(
            snap, proposal, selected_mask_path=mask,
            protected_project_root=protected, bundle_directory=tmp_path / "outside",
        )


def test_c4b2_rejects_stale_source_and_mask(tmp_path):
    snap, proposal, mask, protected = _fixture(tmp_path)
    snap.image_path.write_bytes(b"tampered")
    with pytest.raises(Exception):
        prepare_c4b2_disposable_bundle(
            snap, proposal, selected_mask_path=mask,
            protected_project_root=protected, bundle_directory=tmp_path / "outside",
        )
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize("target", ["source", "mask", "graph", "manifest", "output"])
def test_c4b2_evidence_tamper_fails_closed(tmp_path, target):
    *_, prepared = _prepared(tmp_path)
    data = json.loads((prepared.directory / "c4b2_manifest.json").read_text())
    file = {
        "source": prepared.directory / "input" / data["source_filename"],
        "mask": prepared.directory / "input" / data["mask_filename"],
        "graph": prepared.directory / "c4b2_api_graph.json",
        "manifest": prepared.directory / "c4b2_manifest.json",
        "output": prepared.directory / "output",
    }[target]
    if target == "output":
        file.rmdir()
    else:
        file.write_bytes(b"tampered")
    with pytest.raises((C4B2IsolationError, ValueError, RuntimeError)):
        verify_c4b2_disposable_bundle(prepared.directory)


def test_c4b2_launch_preview_only_and_refuses_shared_port(tmp_path):
    *_, prepared = _prepared(tmp_path)
    python = tmp_path / "python.exe"
    main = tmp_path / "ComfyUI" / "main.py"
    main.parent.mkdir()
    python.write_bytes(b"fake interpreter")
    main.write_text("# fake main")
    argv = preview_c4b2_isolated_launch(
        prepared.directory, python_executable=python, comfyui_main=main
    )
    assert argv[:2] == (str(python), str(main))
    assert argv[argv.index("--listen") + 1] == "127.0.0.1"
    assert argv[argv.index("--port") + 1] == "8298"
    assert argv[argv.index("--input-directory") + 1] == str(prepared.directory / "input")
    assert argv[argv.index("--output-directory") + 1] == str(prepared.directory / "output")
    assert argv[argv.index("--temp-directory") + 1] == str(prepared.directory / "temp")
    assert argv[argv.index("--user-directory") + 1] == str(prepared.directory / "user")
    assert "--disable-auto-launch" in argv
    for port in (8188, 8299, 0, True):
        with pytest.raises(C4B2IsolationError, match="dedicated process"):
            preview_c4b2_isolated_launch(
                prepared.directory, python_executable=python, comfyui_main=main,
                port=port,
            )


def test_c4b2_pixel_audit_reads_external_png_without_claiming_gpu(tmp_path):
    *_, prepared = _prepared(tmp_path)
    data = json.loads((prepared.directory / "c4b2_manifest.json").read_text())
    source_path = prepared.directory / "input" / data["source_filename"]
    mask_path = prepared.directory / "input" / data["mask_filename"]
    with Image.open(source_path) as src, Image.open(mask_path) as mask:
        output = src.copy()
        for y in range(src.height):
            for x in range(src.width):
                if mask.getpixel((x, y)) == 255:
                    output.putpixel((x, y), (180, 100, 80))
    outside = tmp_path / "outside.png"
    output.save(outside)
    with pytest.raises(C4B2IsolationError, match="disposable output"):
        audit_c4b2_external_result(prepared.directory, result_png=outside)
    result_path = prepared.directory / "output" / "synthetic_result.png"
    output.save(result_path)
    report = audit_c4b2_external_result(prepared.directory, result_png=result_path)
    assert report.protected_pixels_identical
    assert report.protected_changed_pixels == 0
    assert report.editable_changed_pixels > 0
    assert not report.provider_inference_verified
    assert not report.candidate_registration_allowed
    output.putpixel((0, 0), (255, 0, 0))
    output.save(result_path)
    changed = audit_c4b2_external_result(prepared.directory, result_png=result_path)
    assert not changed.protected_pixels_identical
    assert changed.protected_changed_pixels == 1
    assert not changed.provider_inference_verified


def test_c4b2_rejects_symlinked_input(tmp_path):
    *_, prepared = _prepared(tmp_path)
    data = json.loads((prepared.directory / "c4b2_manifest.json").read_text())
    source = prepared.directory / "input" / data["source_filename"]
    source.unlink()
    try:
        source.symlink_to(tmp_path / "outside.png")
    except (OSError, NotImplementedError):
        pytest.skip("Symlink privileges unavailable on this platform")
    with pytest.raises(C4B2IsolationError):
        verify_c4b2_disposable_bundle(prepared.directory)


def test_c4b2_static_schema_and_model_inventory_not_gpu_approval(tmp_path):
    *_, prepared = _prepared(tmp_path)
    graph = json.loads((prepared.directory / "c4b2_api_graph.json").read_text())
    classes = {node["class_type"] for node in graph.values()}
    object_info = {
        kind: {
            "input": {
                "required": {
                    name: [["placeholder"], {}]
                    for node in graph.values()
                    if node["class_type"] == kind
                    for name in node["inputs"]
                },
                "optional": {},
            },
            "output": [],
        }
        for kind in classes
    }
    outputs = {
        "LoadImage": ["IMAGE"],
        "LoadImageMask": ["MASK"],
        "GetImageSize": ["INT", "INT"],
        "MaskToImage": ["IMAGE"],
        "ImageScale": ["IMAGE"],
        "ImageToMask": ["MASK"],
        "SetLatentNoiseMask": ["LATENT"],
        "ImageCompositeMasked": ["IMAGE"],
    }
    for kind, output in outputs.items():
        object_info[kind]["output"] = output
    for kind, field, values in (
        ("UNETLoader", "unet_name", [graph["170:161"]["inputs"]["unet_name"]]),
        ("CLIPLoader", "clip_name", [graph["170:162"]["inputs"]["clip_name"]]),
        ("VAELoader", "vae_name", [graph["170:146"]["inputs"]["vae_name"]]),
        ("ImageScale", "upscale_method", ["nearest-exact", "lanczos"]),
        ("LoadImageMask", "channel", ["red", "green", "blue", "alpha"]),
    ):
        object_info[kind]["input"]["required"][field] = [values, {}]
    system = {
        "devices": [
            {
                "name": "RTX 5060 Ti",
                "vram_total": 16 * 1024**3,
                "vram_free": 14 * 1024**3,
            }
        ]
    }
    checked = inspect_c4b2_offline_runtime_schemas(
        prepared.directory, object_info=object_info, system_stats=system
    )
    assert checked.schema_readiness
    assert checked.graph_sha256 == prepared.graph_sha256
    assert "14.0 GiB free" in checked.gpu_devices[0]
    assert not checked.runtime_mask_qualified
    assert not checked.execution_authorized

    object_info["GetImageSize"]["output"] = ["FLOAT", "INT"]
    object_info["UNETLoader"]["input"]["required"]["unet_name"] = [["missing"], {}]
    failed = inspect_c4b2_offline_runtime_schemas(
        prepared.directory, object_info=object_info, system_stats={"devices": None}
    )
    assert not failed.schema_readiness
    assert any("GetImageSize" in x for x in failed.missing_requirements)
    assert any("UNETLoader" in x for x in failed.missing_requirements)
    assert any("GPU" in x for x in failed.missing_requirements)
    assert not failed.execution_authorized
