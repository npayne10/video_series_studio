"""C4B standalone Qwen mask graph: source-bound, fail-closed and no execution."""

import copy
import hashlib
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from vscs.application.caps.c4b_isolated_mask_provider import (
    inspect_c4b_local_node_inventory,
    inspect_c4b_node_schemas,
    prepare_c4b_isolated_blueprint,
    validate_c4b_api_graph,
)
from vscs.application.caps.general_visual_correction_triage import candidate_visual_triage
from vscs.application.caps.geometry_correction_policy import (
    GeometryCorrectionError,
    GeometryDefect,
)
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
    project = tmp_path / "acceptance_project"
    image_folder = project / "Canonical Assets" / "STORY-C4A-TEST" / "Images" / "Visual Candidates"
    image_folder.mkdir(parents=True)
    source_path = image_folder / "candidate.png"
    Image.new("RGB", (320, 256), (20, 40, 60)).save(source_path)
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    snapshot = SimpleNamespace(
        project_root=project.resolve(),
        image_path=source_path.resolve(),
        asset_id="STORY-C4A-TEST",
        reference_id=4,
        image_sha256=digest,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "Three buttons and recessed dial"),
            ("geometry", "Standing console beside independent workstation"),
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
        observation="The rotary dial protrudes instead of being recessed.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=NormalizedRegion(0.2, 0.2, 0.2, 0.3),
    )
    review = propose_spatial_evidence(
        triage,
        previous=review,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="The adjacent workstation is visually separate.",
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
        proposal, source_path=source_path, reviewer_confirmed_mask=True
    )
    mask = save_reviewed_mask_once(
        evidence,
        proposal=proposal,
        source_path=source_path,
        destination_directory=mask_dir,
    )
    return snapshot, proposal, mask, evidence


def test_standalone_graph_is_source_bound_and_xcic_free(tmp_path, monkeypatch):
    snapshot, proposal, mask, evidence = _fixture(tmp_path)
    before_source = snapshot.image_path.read_bytes()
    before_mask = mask.read_bytes()
    # Any transport call from C4B is forbidden; only in-memory construction.
    monkeypatch.setattr(
        "vscs.application.caps.c4b_isolated_mask_provider.inspect_c4b_node_schemas",
        lambda *_args: pytest.fail("C4B preparation must not reach ComfyUI"),
    )
    plan = prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask, seed=1234)
    plan.verify_seal()
    assert plan.binding_contract_verified_offline
    assert plan.source_sha256 == snapshot.image_sha256
    assert plan.mask_sha256 == hashlib.sha256(before_mask).hexdigest()
    assert plan.c1_proposal_sha256 == proposal.proposal_sha256
    assert len(plan.evidence_sha256) == 64
    assert plan.source_input_filename.startswith("c4b_source_")
    assert plan.mask_input_filename.startswith("c4b_mask_")
    assert plan.seed == 1234
    assert plan.output_prefix == "C4B_DISPOSABLE_QUALIFICATION"
    assert not plan.execution_authorized
    assert not plan.input_staging_authorized
    assert not plan.governed_attempt_allowed
    assert not plan.candidate_registration_allowed
    assert not plan.node_schema_verified_live
    assert not plan.runtime_mask_polarity_verified
    assert not plan.runtime_vram_verified
    assert not plan.protected_pixel_fidelity_verified
    assert "XCIC" not in str(plan.graph)
    assert "171" not in plan.graph
    assert plan.graph["C4B_SOURCE"]["inputs"]["image"] == plan.source_input_filename
    assert plan.graph["C4B_MASK"]["inputs"]["image"] == plan.mask_input_filename
    assert plan.graph["170:160"]["inputs"]["image"] == ["C4B_SOURCE", 0]
    assert plan.graph["C4B_MASK_SCALE"]["inputs"]["width"] == ["C4B_EDIT_SIZE", 0]
    assert plan.graph["C4B_MASK_SCALE"]["inputs"]["height"] == ["C4B_EDIT_SIZE", 1]
    assert plan.graph["C4B_LATENT_MASK"]["inputs"]["mask"] == ["C4B_EDIT_MASK", 0]
    assert plan.graph["C4B_COMPOSITE"]["inputs"]["destination"] == ["C4B_SOURCE", 0]
    assert plan.graph["C4B_COMPOSITE"]["inputs"]["mask"] == ["C4B_MASK", 0]
    assert plan.graph["9"]["class_type"] == "SaveImage"
    assert plan.graph["9"]["inputs"]["images"] == ["C4B_COMPOSITE", 0]
    assert snapshot.image_path.read_bytes() == before_source
    assert mask.read_bytes() == before_mask
    assert evidence.source_size == (320, 256)


@pytest.mark.parametrize("seed", [-1, 2**64, 1.0, True, "10"])
def test_seed_is_strict_fixed_u64(tmp_path, seed):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    with pytest.raises(GeometryCorrectionError, match="seed"):
        prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask, seed=seed)


def test_historical_mask_and_stale_source_block_contract(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    digest = hashlib.sha256(mask.read_bytes()).hexdigest()
    older = mask.parent / f"c2-4-ffffffffffffffff-{digest[:16]}.png"
    older.write_bytes(mask.read_bytes())
    with pytest.raises(GeometryCorrectionError, match="HISTORICAL"):
        prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=older)
    snapshot.image_path.write_bytes(b"tampered")
    with pytest.raises(GeometryCorrectionError, match="source changed"):
        prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask)


@pytest.mark.parametrize(
    "tamper",
    [
        ("C4B_MASK_SCALE", "upscale_method", "bilinear"),
        ("C4B_COMPOSITE", "destination", ["170:160", 0]),
        ("C4B_COMPOSITE", "mask", ["C4B_EDIT_MASK", 0]),
        ("C4B_LATENT_MASK", "mask", ["C4B_MASK", 0]),
        ("9", "filename_prefix", "../unsafe"),
    ],
)
def test_graph_tampering_rejected(tmp_path, tamper):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    original = prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask)
    changed = copy.deepcopy(original.graph)
    node, field, value = tamper
    changed[node]["inputs"][field] = value
    with pytest.raises(GeometryCorrectionError, match="C4B"):
        validate_c4b_api_graph(changed)
    with pytest.raises(GeometryCorrectionError, match="graph changed"):
        replace(original, graph=changed).verify_seal()


def test_reject_extra_provider_node_and_dangling_edge(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    plan = prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask)
    extra = copy.deepcopy(plan.graph)
    extra["evil"] = {"class_type": "CustomShellRunner", "inputs": {}}
    with pytest.raises(GeometryCorrectionError, match="differs"):
        validate_c4b_api_graph(extra)
    missing = copy.deepcopy(plan.graph)
    missing["170:161"]["inputs"]["unet_name"] = ["missing_model_loader", 0]
    with pytest.raises(GeometryCorrectionError, match="dangling"):
        validate_c4b_api_graph(missing)


def test_c4b_node_schema_inventory_is_read_only(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    plan = prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask)
    classes = {node["class_type"] for node in plan.graph.values()}
    schemas = {
        kind: {
            "input": {
                "required": {
                    key: ["STRING", {}]
                    for node in plan.graph.values()
                    if node["class_type"] == kind
                    for key in node["inputs"]
                },
                "optional": {},
            }
        }
        for kind in classes
    }
    assert inspect_c4b_node_schemas(plan.graph, schemas) == ()
    del schemas["GetImageSize"]
    problems = inspect_c4b_node_schemas(plan.graph, schemas)
    assert any("GetImageSize" in x for x in problems)
    schemas["GetImageSize"] = {"input": {"required": {"image": ["IMAGE", {}]}, "optional": {}}}
    del schemas["ImageScale"]["input"]["required"]["width"]
    problems = inspect_c4b_node_schemas(plan.graph, schemas)
    assert any("ImageScale" in x and "width" in x for x in problems)


def test_c4b_full_evidence_seal_rejects_identity_tampering(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    plan = prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask)
    for changed in (
        replace(plan, source_sha256="a" * 64),
        replace(plan, mask_sha256="b" * 64),
        replace(plan, c1_proposal_sha256="c" * 64),
        replace(plan, managed_template_sha256="d" * 64),
        replace(plan, output_prefix="C4B_UNREVIEWED_OUTPUT"),
    ):
        with pytest.raises(GeometryCorrectionError, match="evidence seal"):
            changed.verify_seal()


def test_changed_prompt_seal_and_fake_xcic_node_rejected(tmp_path):
    snapshot, proposal, mask, _ = _fixture(tmp_path)
    plan = prepare_c4b_isolated_blueprint(snapshot, proposal, selected_mask_path=mask)
    different = copy.deepcopy(plan.graph)
    different["170:151"]["inputs"]["prompt"] += " (unreviewed instruction)"
    with pytest.raises(GeometryCorrectionError, match="graph changed"):
        replace(plan, graph=different).verify_seal()
    extra = copy.deepcopy(plan.graph)
    extra["evil"] = {"class_type": "XCICQwenReferenceJobLoader", "inputs": {}}
    with pytest.raises(GeometryCorrectionError, match="XCIC"):
        validate_c4b_api_graph(extra)


def test_get_only_inventory_never_confers_gpu_authority(monkeypatch):
    from vscs.application.caps.c4b_isolated_mask_provider import _REQUIRED_INPUTS

    info = {
        kind: {
            "input": {
                "required": {key: ["STRING", {}] for key in fields},
                "optional": {},
            }
        }
        for kind, fields in _REQUIRED_INPUTS.items()
    }
    requests: list[tuple[str, float]] = []

    def fake_get(url: str, timeout: float):
        requests.append((url, timeout))
        return info, {
            "devices": [
                {
                    "name": "RTX 5060 Ti",
                    "vram_total": 16 * 1024**3,
                    "vram_free": 12 * 1024**3,
                }
            ]
        }

    monkeypatch.setattr("vscs.application.caps.c4b_isolated_mask_provider._inventory", fake_get)
    report = inspect_c4b_local_node_inventory()
    assert requests == [("http://127.0.0.1:8188", 3.0)]
    assert not report.missing_mask_node_classes
    assert not report.missing_input_names
    assert len(report.present_mask_node_classes) == len(_REQUIRED_INPUTS)
    assert "12.0 GiB free" in report.describe()
    assert not report.execution_authorized
    assert not report.gpu_generation_verified
    del info["ImageScale"]["input"]["required"]["width"]
    del info["GetImageSize"]
    info["LoadImageMask"]["input"]["required"] = {}
    invalid = inspect_c4b_local_node_inventory()
    assert "GetImageSize" in invalid.missing_mask_node_classes
    assert any("ImageScale" in detail for detail in invalid.missing_input_names)
    assert any("LoadImageMask" in detail for detail in invalid.missing_input_names)
    assert invalid.blockers


def test_malformed_gpu_info_remains_an_unverified_blocker(monkeypatch):
    from vscs.application.caps.c4b_isolated_mask_provider import _REQUIRED_INPUTS

    schemas = {
        kind: {
            "input": {
                "required": {key: [] for key in fields},
                "optional": {},
            }
        }
        for kind, fields in _REQUIRED_INPUTS.items()
    }
    monkeypatch.setattr(
        "vscs.application.caps.c4b_isolated_mask_provider._inventory",
        lambda *_args: (schemas, {"devices": None}),
    )
    result = inspect_c4b_local_node_inventory()
    assert not result.gpu_devices
    assert any("GPU" in item for item in result.blockers)
    assert not result.execution_authorized
