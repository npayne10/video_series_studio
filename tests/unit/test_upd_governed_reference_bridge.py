"""Phase 20.18.2 governed reference-plan bridge tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vscs.application.acpp.models import (
    AudioSpecification,
    ClipIdentity,
    ClipProductionPackage,
    ContinuityBinding,
    OutputSpecification,
    PromptSpecification,
    RenderSpecification,
)
from vscs.application.acpp.reference_roles import (
    ReferenceClass,
    ReferenceCoverage,
    ReferencePlan,
    ReferencePriority,
    ReferenceRole,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)
from vscs.application.acpp.serialization import ACPPSerializer
from vscs.application.governed_reference_plan_source import (
    PersistedGovernedReferencePlanSource,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self) -> None:
        self.value = ProductionPackage(
            package_id="PP-SHT-001-A",
            shot_id="SHT-001",
            schema_version="1.0",
            source_fingerprint="source",
            package_fingerprint="fingerprint",
            provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
            story_context={"scene": "Observation Deck"},
            shot={"title": "Reference test"},
            assets=(),
            camera={"production": {"shot_size": "wide", "movement": "static"}},
            lighting={"production": {"lighting_intent": "natural"}},
            environment={"environment_context": "exterior"},
            action_performance={"production": {"temporal_narrative": "The vessel holds position."}},
            continuity={"production": {}},
            style={"production": {"provider_neutral": True}},
            dialogue=(),
            effects=(),
            references=(),
            universal_description={},
            provider_outputs={},
            validation={
                "action_performance_complete": True,
                "assets_complete": True,
                "camera_complete": True,
                "lighting_complete": True,
                "continuity_complete": True,
                "style_complete": True,
            },
            status=ProductionPackageStatus.COMPILING,
        )

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value

    def _append_derived(self, current: ProductionPackage, data: dict):
        derived = replace(
            current,
            package_id="PP-SHT-001-UPD",
            package_fingerprint="upd-fingerprint",
            universal_description=dict(data["universal_description"]),
            validation=dict(data["validation"]),
            status=ProductionPackageStatus.COMPILING,
        )
        self.value = derived
        return derived


class _ReferencePlans:
    def __init__(self, plan: dict | None) -> None:
        self.plan = plan

    def reference_plan_for_shot(self, shot_id: str):
        assert shot_id == "SHT-001"
        return None if self.plan is None else dict(self.plan)


def _plan(reference_id: str = "REF-JAMES-16X9") -> dict:
    return {
        "schema_version": "1.0",
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": None,
            "aspect_tolerance": 0.03,
        },
        "references": [
            {
                "reference_id": reference_id,
                "asset_id": "CAP-CHR-001",
                "role": "primary_identity",
                "reference_class": "provider_ready_derivative",
                "priority": "required",
                "subject_type": "character",
                "source_path": "references/james-16x9.png",
                "canonical_source_id": "CAP-CHR-001-MASTER",
                "label": "James Spence video identity",
                "width": 1280,
                "height": 720,
                "provider_ready": True,
                "provider_profiles": [],
                "coverage": {
                    "framing_type": "full_body",
                    "coverage": "full_required_asset",
                    "required_features_visible": True,
                    "identity_visible": True,
                    "full_required_asset_visible": True,
                },
                "reference_fingerprint": "stale-fingerprint",
                "file_checksum": "stale-checksum",
                "contains_subjects": ["James Spence"],
                "contains_props": [],
                "contains_environments": [],
            }
        ],
    }


def test_upd_propagates_authoritative_governed_reference_plan(tmp_path: Path) -> None:
    packages = _Packages()
    plans = _ReferencePlans(_plan())
    service = UniversalProductionDescriptionCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        plans,  # type: ignore[arg-type]
    )

    draft = service.create_from_current_package("SHT-001")
    assert draft.description_value()["reference_plan"] == _plan()

    service.mark_ready("SHT-001")
    production = packages.value.universal_description["production"]
    assert production["reference_plan"] == _plan()
    assert production["canonical_references"] == []


def test_governed_reference_plan_change_marks_upd_stale(tmp_path: Path) -> None:
    packages = _Packages()
    plans = _ReferencePlans(_plan())
    service = UniversalProductionDescriptionCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        plans,  # type: ignore[arg-type]
    )

    draft = service.create_from_current_package("SHT-001")
    plans.plan = _plan("REF-JAMES-16X9-V2")

    assert not service.is_current(draft)
    refreshed = service.rebase_to_current_package("SHT-001")
    assert service.is_current(refreshed)
    assert refreshed.description_value()["reference_plan"]["references"][0]["reference_id"] == (
        "REF-JAMES-16X9-V2"
    )


def test_legacy_upd_omits_reference_plan_when_no_governed_plan_exists(tmp_path: Path) -> None:
    packages = _Packages()
    service = UniversalProductionDescriptionCompilerService(
        _Projects(tmp_path),  # type: ignore[arg-type]
        packages,  # type: ignore[arg-type]
        _ReferencePlans(None),  # type: ignore[arg-type]
    )

    draft = service.create_from_current_package("SHT-001")
    assert "reference_plan" not in draft.description_value()

    service.mark_ready("SHT-001")
    assert "reference_plan" not in packages.value.universal_description["production"]


def test_default_reference_plan_source_reads_persisted_acpp_authority(tmp_path: Path) -> None:
    reference = ShotReference(
        reference_id="REF-JAMES-16X9",
        role=ReferenceRole.PRIMARY_IDENTITY,
        reference_class=ReferenceClass.PROVIDER_READY_DERIVATIVE,
        priority=ReferencePriority.REQUIRED,
        subject_type=ReferenceSubjectType.CHARACTER,
        source_path="references/james-16x9.png",
        asset_id="CAP-CHR-001",
        provider_ready=True,
        width=1280,
        height=720,
        coverage=ReferenceCoverage(
            framing_type="full_body",
            coverage="full_required_asset",
            required_features_visible=True,
            identity_visible=True,
            full_required_asset_visible=True,
        ),
    )
    acpp = ClipProductionPackage(
        identity=ClipIdentity(
            clip_id="CLIP-001",
            production_id="EP01",
            episode_id="EP01",
            scene_id="SCN-001",
            shot_id="SHT-001",
        ),
        render=RenderSpecification(
            width=1280,
            height=720,
            frames_per_second=24,
            frame_count=145,
        ),
        assets=(),
        prompt=PromptSpecification(positive_visual_intent="James stands in frame."),
        continuity=ContinuityBinding(),
        audio=AudioSpecification(),
        output=OutputSpecification(relative_directory="renders", filename_stem="CLIP-001"),
        reference_plan=ReferencePlan(
            target=ReferenceTarget(
                width=1280,
                height=720,
                profile_id="production-video-16x9",
            ),
            references=(reference,),
        ),
    )
    path = tmp_path / "story" / "acpp" / "CLIP-001.json"
    path.parent.mkdir(parents=True)
    path.write_text(ACPPSerializer().dumps(acpp), encoding="utf-8")

    source = PersistedGovernedReferencePlanSource(_Projects(tmp_path))  # type: ignore[arg-type]
    payload = source.reference_plan_for_shot("sht-001")

    assert payload is not None
    assert payload["target"]["width"] == 1280
    assert payload["target"]["height"] == 720
    assert payload["references"][0]["reference_id"] == "REF-JAMES-16X9"
    assert payload["references"][0]["role"] == "primary_identity"
