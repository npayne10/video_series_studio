from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.production_execution import CompiledProductionPackage
from vscs.infrastructure.production_execution.current_authority_backend import (
    CurrentAuthorityLTX23V721ProductionPackageCompilationService,
)
from vscs.infrastructure.production_execution.ltx23_v721_backend import (
    LocalLTX23V721ProductionPackageCompilationService,
)
from vscs.infrastructure.production_execution.package_compilation import (
    LocalProductionPackageCompilationError,
)


def _reference(
    tmp_path: Path,
    *,
    reference_id: str,
    asset_id: str,
    role: str,
    filename: str,
) -> dict[str, object]:
    path = tmp_path / "references" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(reference_id.encode("utf-8"))
    return {
        "reference_id": reference_id,
        "role": role,
        "reference_class": "provider_ready_derivative",
        "priority": "required",
        "subject_type": "environment" if role == "environment_reference" else "character",
        "source_path": str(path.relative_to(tmp_path)),
        "canonical_source_id": f"CANONICAL-{asset_id}",
        "asset_id": asset_id,
        "label": f"{asset_id} governed reference",
        "width": 1280,
        "height": 720,
        "provider_ready": True,
        "provider_profiles": ["production-video-16x9"],
        "coverage": {
            "required_features_visible": True,
            "identity_visible": role != "environment_reference",
            "full_required_asset_visible": True,
        },
        "file_checksum": f"checksum-{reference_id}",
        "reference_fingerprint": f"fingerprint-{reference_id}",
    }


def _plan(tmp_path: Path, *, include_continuity: bool = False) -> dict[str, object]:
    references = [
        _reference(
            tmp_path,
            reference_id="REF-JAMES-001",
            asset_id="CHR-JAMES",
            role="primary_identity",
            filename="james.png",
        ),
        _reference(
            tmp_path,
            reference_id="REF-SANDRA-001",
            asset_id="CHR-SANDRA",
            role="secondary_identity",
            filename="sandra.png",
        ),
        _reference(
            tmp_path,
            reference_id="REF-BRIDGE-001",
            asset_id="LOC-MAURITANIA-BRIDGE",
            role="environment_reference",
            filename="bridge.png",
        ),
    ]
    if include_continuity:
        references.append(
            _reference(
                tmp_path,
                reference_id="REF-PREVIOUS-SHOT-001",
                asset_id="SHT-PREVIOUS",
                role="start_frame_reference",
                filename="previous-shot-final.png",
            )
        )
    return {
        "schema_version": "1.0",
        "status": "passed",
        "target": {"width": 1280, "height": 720},
        "references": references,
        "diagnostics": [],
    }


def _compiled(reference_plan: dict[str, object]) -> CompiledProductionPackage:
    production_authority = {
        "dialogue": [
            {
                "speaker": "Sandra Crawford",
                "text": "Trajectory confirmed, Commander.",
            }
        ]
    }
    return CompiledProductionPackage(
        task_id="PT-VIDEO-001",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id="SHT-002",
        profile="production",
        authority_id="UPD-SHT-002",
        authority_revision=1,
        authority_fingerprint="authority-fingerprint",
        approved_by="human-reviewer",
        source_package_id="PP-SHT-002",
        source_package_fingerprint="source-package-fingerprint",
        source_schema_version="1.0",
        universal_text="Sandra stands beside James on the Mauritania bridge.",
        positive_prompt="Sandra stands beside James on the Mauritania bridge.",
        negative_prompt="identity drift, malformed anatomy",
        previous_approved_final_frame=None,
        filename_prefix="VSCS/Production/SHT-002",
        width=1280,
        height=720,
        frame_count=145,
        frames_per_second=24,
        cfg=1.25,
        ic_lora_strength=0.46,
        seed=56971365581327,
        composition_plan={"mode": "two_character_dialogue"},
        production_authority=production_authority,
        package_fingerprint="provider-neutral-fingerprint",
        reference_plan=reference_plan,
    )


def test_v721_boundary_emits_provider_multi_reference_from_real_bindings(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    payload = service._comfyui_payload(_compiled(plan))

    reference_plan = payload["reference_plan"]
    contract = reference_plan["provider_multi_reference"]
    assert contract["mode"] == "ltx_ingredients_iclora"
    assert contract["collapsed_scene_anchor"] is False
    assert contract["reference_count"] == 3
    assert [item["role"] for item in contract["references"]] == [
        "primary_identity",
        "secondary_identity",
        "environment_reference",
    ]
    assert [Path(item["path"]) for item in contract["references"]] == [
        (tmp_path / "references" / "james.png").resolve(strict=False),
        (tmp_path / "references" / "sandra.png").resolve(strict=False),
        (tmp_path / "references" / "bridge.png").resolve(strict=False),
    ]
    assert all(item["provider_ready"] is True for item in contract["references"])


def test_v721_boundary_keeps_continuity_out_of_visual_reference_slots(tmp_path: Path) -> None:
    plan = _plan(tmp_path, include_continuity=True)
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    payload = service._comfyui_payload(_compiled(plan))

    contract = payload["reference_plan"]["provider_multi_reference"]
    assert contract["reference_count"] == 3
    assert "start_frame_reference" not in {item["role"] for item in contract["references"]}
    assert contract["continuity_policy"]["prompt_mode"] == "preserve_shot_to_shot_continuity"
    assert contract["continuity"] == {
        "role": "previous_approved_shot_final_frame",
        "path": str((tmp_path / "references" / "previous-shot-final.png").resolve(strict=False)),
        "file_checksum": "checksum-REF-PREVIOUS-SHOT-001",
        "reference_fingerprint": "fingerprint-REF-PREVIOUS-SHOT-001",
        "provider_ready": True,
        "authority": "strong",
        "prompt_mode": "preserve_shot_to_shot_continuity",
    }


def test_v721_boundary_rejects_missing_governed_reference_path(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    references = plan["references"]
    assert isinstance(references, list)
    first = references[0]
    assert isinstance(first, dict)
    first["source_path"] = "references/does-not-exist.png"
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    with pytest.raises(
        LocalProductionPackageCompilationError,
        match="Governed provider reference file does not exist",
    ):
        service._comfyui_payload(_compiled(plan))


def test_v721_provider_enrichment_does_not_mutate_neutral_reference_or_dialogue_authority(
    tmp_path: Path,
) -> None:
    plan = _plan(tmp_path)
    compiled = _compiled(plan)
    dialogue_before = [dict(item) for item in compiled.production_authority["dialogue"]]
    service = LocalLTX23V721ProductionPackageCompilationService(tmp_path)

    payload = service._comfyui_payload(compiled)

    assert "provider_multi_reference" not in plan
    assert "bindings" not in plan
    assert compiled.reference_plan is plan
    assert compiled.production_authority["dialogue"] == dialogue_before
    assert payload["production_authority"]["dialogue"] == dialogue_before
    assert payload["shot_prompt"] == compiled.positive_prompt
    assert payload["acpp"]["prompts"]["positive"] == compiled.positive_prompt


def test_current_authority_compiler_inherits_single_v721_reference_enrichment_seam() -> None:
    assert (
        CurrentAuthorityLTX23V721ProductionPackageCompilationService._provider_reference_plan
        is LocalLTX23V721ProductionPackageCompilationService._provider_reference_plan
    )
