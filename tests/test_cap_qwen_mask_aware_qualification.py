"""F5.4.1B offline experimental mask graph and protected pixel evidence."""

import copy
import json

import pytest
from PIL import Image

from vscs.application.caps.qwen_mask_aware_qualification import (
    MaskAwareQualificationError,
    build_experimental_masked_graph,
    confirm_preserved_pixels,
    create_binary_edit_mask,
    prepare_mask_aware_bundle,
    validate_experimental_graph,
)


def _source(tmp_path):
    project = tmp_path / "active_project"
    project.mkdir()
    source = project / "candidate4.png"
    Image.new("RGB", (320, 256), (40, 60, 80)).save(source)
    return project, source


def test_offline_graph_has_latent_mask_and_post_decode_protective_composite():
    graph = build_experimental_masked_graph()
    validate_experimental_graph(graph)
    assert graph["F541B_MASK"]["class_type"] == "LoadImageMask"
    assert graph["F541B_MASK"]["inputs"]["channel"] == "red"
    assert graph["F541B_LATENT_MASK"]["inputs"]["samples"] == ["170:156", 0]
    assert graph["F541B_LATENT_MASK"]["inputs"]["mask"] == ["F541B_MASK", 0]
    assert graph["170:169"]["inputs"]["latent_image"] == ["F541B_LATENT_MASK", 0]
    assert graph["F541B_COMPOSITE"]["inputs"]["destination"] == ["170:160", 0]
    assert graph["F541B_COMPOSITE"]["inputs"]["source"] == ["170:158", 0]
    assert graph["F541B_COMPOSITE"]["inputs"]["mask"] == ["F541B_MASK", 0]
    assert graph["9"]["inputs"]["images"] == ["F541B_COMPOSITE", 0]
    assert graph["170:169"]["inputs"]["denoise"] == 1
    assert graph["F541B_MASK"]["inputs"]["image"].startswith("__F541B_")


def test_disconnected_mask_or_composite_refused():
    graph = build_experimental_masked_graph()
    bad = copy.deepcopy(graph)
    bad["170:169"]["inputs"]["latent_image"] = ["170:156", 0]
    with pytest.raises(MaskAwareQualificationError, match="unreviewed"):
        validate_experimental_graph(bad)
    bad = copy.deepcopy(graph)
    bad["9"]["inputs"]["images"] = ["170:158", 0]
    with pytest.raises(MaskAwareQualificationError, match="unreviewed"):
        validate_experimental_graph(bad)


def test_mask_is_binary_bounded_and_not_a_CAP_mask(tmp_path):
    _project, source = _source(tmp_path)
    target = tmp_path / "mask.png"
    report = create_binary_edit_mask(source, target, (100, 50, 140, 100))
    assert not report.execution_authorized
    assert report.mask_coverage_percent > 0
    assert not report.gpu_inference_verified
    with Image.open(target) as mask:
        assert mask.mode == "L"
        assert mask.getpixel((120, 60)) == 255
        assert mask.getpixel((0, 0)) == 0
    with pytest.raises(MaskAwareQualificationError, match="already exists"):
        create_binary_edit_mask(source, target, (100, 50, 140, 100))


def test_extreme_and_outside_mask_bounds_refused(tmp_path):
    _project, source = _source(tmp_path)
    target = tmp_path / "mask.png"
    for bounds in ((0, 0, 321, 10), (2, 2, 2, 10), (0, 0, 320, 256)):
        with pytest.raises(MaskAwareQualificationError):
            create_binary_edit_mask(source, target, bounds)
    assert not target.exists()


def test_offline_qualification_creates_only_external_evidence(tmp_path):
    project, source = _source(tmp_path)
    bundle = tmp_path / "outside" / "run_001"
    bundle.parent.mkdir()
    report = prepare_mask_aware_bundle(
        source_png=source, project_root=project, bundle_directory=bundle,
        bounds=(100, 50, 140, 100),
    )
    assert not report.execution_authorized
    assert not report.mask_comfyui_input_bound
    assert sorted(p.name for p in bundle.iterdir()) == [
        "experimental_masked_api.json",
        "mask.png",
        "qualification_manifest.json",
        "roi_preview.png",
        "source.png",
    ]
    manifest = json.loads((bundle / "qualification_manifest.json").read_text())
    assert manifest["gpu_execution_authorized"] is False
    assert manifest["roi_preview_sha256"]
    with Image.open(bundle / "roi_preview.png") as preview:
        assert preview.getpixel((120, 75)) != (40, 60, 80)
        assert preview.getpixel((0, 0)) == (40, 60, 80)
    assert manifest["candidate_registration_allowed"] is False
    assert manifest["correction_attempt_reserved"] is False
    assert source.is_file()
    with pytest.raises(MaskAwareQualificationError, match="already exists"):
        prepare_mask_aware_bundle(
            source_png=source, project_root=project, bundle_directory=bundle,
            bounds=(100, 50, 140, 100),
        )


def test_never_allow_bundle_inside_active_project(tmp_path):
    project, source = _source(tmp_path)
    with pytest.raises(RuntimeError, match="outside"):
        prepare_mask_aware_bundle(
            source_png=source, project_root=project,
            bundle_directory=project / "bad_bundle",
            bounds=(100, 50, 140, 100),
        )


def test_protected_pixel_audit_detects_single_outside_change(tmp_path):
    _project, source = _source(tmp_path)
    mask_path = tmp_path / "mask.png"
    create_binary_edit_mask(source, mask_path, (100, 50, 140, 100))
    composite = tmp_path / "composite.png"
    with Image.open(source) as src:
        result = src.copy()
    result.putpixel((120, 75), (255, 255, 255))
    result.save(composite)
    audit = confirm_preserved_pixels(source, composite, mask_path)
    assert audit["outside_mask_pixels_identical"] is True
    assert audit["protected_changed_pixels"] == 0
    result.putpixel((0, 0), (255, 255, 255))
    result.save(composite)
    audit = confirm_preserved_pixels(source, composite, mask_path)
    assert audit["outside_mask_pixels_identical"] is False
    assert audit["protected_changed_pixels"] == 1
    assert audit["semantic_geometry_correct"] is None


def test_edited_image_dimensions_must_match_mask(tmp_path):
    project, source = _source(tmp_path)
    mask_path = tmp_path / "mask.png"
    create_binary_edit_mask(source, mask_path, (100, 50, 140, 100))
    edited = tmp_path / "edited.png"
    Image.new("RGB", (300, 256), (50, 50, 50)).save(edited)
    with pytest.raises(MaskAwareQualificationError, match="must match"):
        confirm_preserved_pixels(source, edited, mask_path)
