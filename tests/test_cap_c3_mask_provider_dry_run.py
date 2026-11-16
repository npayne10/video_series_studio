"""F5.4.2 C3: offline mask preflight never queues, stages or grants authority."""

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from vscs.application.caps.c3_mask_provider_dry_run import (
    _inventory,
    inspect_c3_mask_dry_run,
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


def _source_and_proposal(tmp_path: Path):
    root = tmp_path.resolve()
    asset = "STORY-C3-TEST"
    directory = root / "Canonical Assets" / asset / "Images" / "Visual Candidates"
    directory.mkdir(parents=True)
    source = directory / "candidate.png"
    Image.new("RGB", (320, 256), (40, 70, 90)).save(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    snapshot = SimpleNamespace(
        project_root=root,
        image_path=source,
        asset_id=asset,
        reference_id=4,
        image_sha256=digest,
        reference_role="supplementary",
        reference_status="candidate",
        accepted_fields=(
            ("components", "A row of three round controls with recessed rotary dial"),
            ("geometry", "A separate workstation stands alongside the console"),
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
        observation="Rotary dial is visibly protruding from the control shelf.",
        defect=GeometryDefect.PROTRUDING_INSTEAD_OF_RECESSED,
        region=NormalizedRegion(0.2, 0.2, 0.2, 0.3),
    )
    review = propose_spatial_evidence(
        triage,
        previous=review,
        field="geometry",
        status=VisualEvidenceStatus.VERIFIED_BY_OPERATOR,
        observation="The adjacent workstation remains visually separate.",
    )
    proposal = prepare_governed_correction_proposal(
        review,
        target_field="components",
        expected_source_sha256=digest,
        reviewer_confirmed_roi=True,
    )
    mask_directory = root / "Canonical Assets" / asset / ".metadata" / "spatial_masks"
    mask_directory.mkdir(parents=True)
    evidence = prepare_reviewed_mask(proposal, source_path=source, reviewer_confirmed_mask=True)
    path = save_reviewed_mask_once(
        evidence,
        proposal=proposal,
        source_path=source,
        destination_directory=mask_directory,
    )
    return snapshot, proposal, path


def test_offline_dry_run_reads_only_and_reports_current_proposal(tmp_path, monkeypatch):
    snapshot, proposal, mask = _source_and_proposal(tmp_path)
    raw_source = snapshot.image_path.read_bytes()
    raw_mask = mask.read_bytes()
    monkeypatch.setattr(
        "vscs.application.caps.c3_mask_provider_dry_run._get_json",
        lambda *_args: pytest.fail("Offline C3 must never contact ComfyUI"),
    )
    report = inspect_c3_mask_dry_run(snapshot, proposal, selected_mask_path=mask)
    assert report.selected_mask_current
    assert report.selected_mask_sha256 == hashlib.sha256(raw_mask).hexdigest()
    assert report.managed_workflow_sha256
    assert report.graph_topology_inspected
    assert not report.endpoint_probed
    assert not report.execution_authorized
    assert not report.mask_provider_compatibility_verified
    assert not report.protected_pixels_verified
    assert not report.governed_attempt_allowed
    assert not report.candidate_registration_allowed
    assert any("Managed Qwen" in item for item in report.blockers)
    assert snapshot.image_path.read_bytes() == raw_source
    assert mask.read_bytes() == raw_mask
    assert sorted(p.name for p in mask.parent.iterdir()) == [mask.name]


def test_unselected_or_historical_mask_stays_blocked(tmp_path):
    snapshot, proposal, mask = _source_and_proposal(tmp_path)
    report = inspect_c3_mask_dry_run(snapshot, proposal, selected_mask_path=None)
    assert not report.selected_mask_current
    assert any("explicitly selected" in item for item in report.blockers)
    digest = hashlib.sha256(mask.read_bytes()).hexdigest()
    other = mask.parent / f"c2-4-ffffffffffffffff-{digest[:16]}.png"
    other.write_bytes(mask.read_bytes())
    report = inspect_c3_mask_dry_run(snapshot, proposal, selected_mask_path=other)
    assert not report.selected_mask_current
    assert any("HISTORICAL" in item for item in report.blockers)
    assert not report.execution_authorized


def test_changed_source_refuses_preflight(tmp_path):
    snapshot, proposal, mask = _source_and_proposal(tmp_path)
    snapshot.image_path.write_bytes(b"changed")
    with pytest.raises(GeometryCorrectionError, match="source changed"):
        inspect_c3_mask_dry_run(snapshot, proposal, selected_mask_path=mask)


def test_comfyui_inventory_uses_only_get_and_refuses_remote(monkeypatch):
    calls: list[str] = []

    def fake_get(_base: str, path: str, _timeout: float):
        calls.append(path)
        if path == "/object_info":
            return {
                name: {
                    "input": {
                        "required": {key: ["STRING", {}] for key in inputs},
                        "optional": {},
                    }
                }
                for name, inputs in {
                    "LoadImageMask": {"image", "channel"},
                    "SetLatentNoiseMask": {"samples", "mask"},
                    "ImageCompositeMasked": {
                        "destination",
                        "source",
                        "mask",
                        "x",
                        "y",
                        "resize_source",
                    },
                }.items()
            }
        return {"devices": [{"name": "RTX 5060 Ti", "vram_total": 16 * 1024**3}]}

    monkeypatch.setattr("vscs.application.caps.c3_mask_provider_dry_run._get_json", fake_get)
    info, stats = _inventory("http://127.0.0.1:8188", 3)
    assert set(info) == {"LoadImageMask", "SetLatentNoiseMask", "ImageCompositeMasked"}
    assert len(stats["devices"]) == 1
    assert calls == ["/object_info", "/system_stats"]
    with pytest.raises(ValueError, match="loopback"):
        _inventory("https://example.org", 3)
    with pytest.raises(GeometryCorrectionError, match="timeout"):
        _inventory("http://127.0.0.1:8188", 0)


def test_local_probe_retains_nonexecution_boundary(tmp_path, monkeypatch):
    snapshot, proposal, mask = _source_and_proposal(tmp_path)
    monkeypatch.setattr(
        "vscs.application.caps.c3_mask_provider_dry_run._inventory",
        lambda *_args: (
            {
                "LoadImageMask": {"input": {"required": {"image": [], "channel": []}}},
                "SetLatentNoiseMask": {"input": {"required": {"samples": [], "mask": []}}},
                "ImageCompositeMasked": {
                    "input": {
                        "required": {
                            "destination": [],
                            "source": [],
                            "mask": [],
                            "x": [],
                            "y": [],
                            "resize_source": [],
                        }
                    }
                },
            },
            {"devices": [{"name": "RTX 5060 Ti", "vram_total": 16 * 1024**3}]},
        ),
    )
    report = inspect_c3_mask_dry_run(
        snapshot, proposal, selected_mask_path=mask, probe_local_comfyui=True
    )
    assert report.endpoint_probed
    assert len(report.remote_nodes_reported) == 3
    assert not report.execution_authorized
    assert not report.mask_provider_compatibility_verified
    assert not report.protected_pixels_verified
    assert report.blockers
