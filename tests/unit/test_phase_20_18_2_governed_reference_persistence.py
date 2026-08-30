from __future__ import annotations

import struct
import zlib
from pathlib import Path

from vscs.application.acpp import (
    ProviderReadyReferenceResolver,
    ReferenceClass,
    ReferenceCoverage,
    ReferencePriority,
    ReferenceRole,
    ReferenceRoleRequest,
    ReferenceSubjectType,
    ReferenceTarget,
    ShotReference,
)
from vscs.application.governed_reference_plan_persistence import (
    GovernedReferencePlanPersistenceService,
)
from vscs.application.governed_reference_plan_source import (
    PersistedGovernedReferencePlanSource,
)
from vscs.application.production_execution.package_compilation import (
    ProductionPackageCompilerService,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.production_tasks import (
    ProductionAuthorityType,
    ProductionCapability,
    ProductionTask,
    ProductionTaskAuthority,
    ProductionTaskState,
    ProductionTaskType,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerService,
)


class _Projects:
    def __init__(self, project_directory: Path) -> None:
        self.project_directory = project_directory


class _Catalog:
    def __init__(self, references: tuple[ShotReference, ...] = ()) -> None:
        self.references = references

    def references_for_asset(self, asset_id: str) -> tuple[ShotReference, ...]:
        return tuple(item for item in self.references if item.asset_id == asset_id)


def _png(path: Path, width: int = 1280, height: int = 720) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    raw = (b"\x00" + (b"\x00\x00\x00" * width)) * height
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 1))
        + chunk(b"IEND", b"")
    )


def _reference(path: Path) -> ShotReference:
    return ShotReference(
        reference_id="REF-JAMES-PROVIDER-READY",
        asset_id="CAP-CHR-001",
        role=ReferenceRole.PRIMARY_IDENTITY,
        reference_class=ReferenceClass.PROVIDER_READY_DERIVATIVE,
        priority=ReferencePriority.REQUIRED,
        subject_type=ReferenceSubjectType.CHARACTER,
        source_path=str(path),
        canonical_source_id="CAP-CHR-001-MASTER",
        label="Commander James Spence provider-ready identity",
        width=1280,
        height=720,
        provider_ready=True,
        provider_profiles=("production-video-16x9",),
        coverage=ReferenceCoverage(
            framing_type="full_body",
            coverage="full_required_asset",
            required_features_visible=True,
            identity_visible=True,
            full_required_asset_visible=True,
        ),
    )


def _source(compiled_upd: dict[str, object]) -> ProductionPackage:
    return ProductionPackage(
        package_id="PP-EP-001-SCN-001-SHT-001-PERSISTED",
        shot_id="EP-001-SCN-001-SHT-001",
        schema_version="1.0",
        source_fingerprint="planning-source",
        package_fingerprint="upd-source-fingerprint",
        provenance=ProductionPackageProvenance(
            integrated_package_id="IPP-SHT-001",
            integrated_package_fingerprint="integrated-fingerprint",
            planning_review_id="REVIEW-SHT-001",
            planning_review_fingerprint="review-fingerprint",
        ),
        story_context={},
        shot={},
        assets=(),
        camera={},
        lighting={},
        environment={},
        action_performance={},
        continuity={},
        style={},
        dialogue=(),
        effects=(),
        references=(),
        universal_description=compiled_upd,
        provider_outputs={},
        validation={
            "universal_description_complete": True,
            "cross_authority_consistent": True,
        },
        status=ProductionPackageStatus.COMPILING,
    )


def _task(source: ProductionPackage) -> ProductionTask:
    fingerprint = ProductionPackageCompilerService.authority_fingerprint(source)
    return ProductionTask(
        task_id="PT-GOVERNED-PERSISTENCE",
        production_id="XORIX",
        episode_id="EP-001",
        scene_id="SCN-001",
        shot_id=source.shot_id,
        task_type=ProductionTaskType.VIDEO_GENERATION,
        authority=ProductionTaskAuthority(
            authority_type=ProductionAuthorityType.UNIVERSAL_PRODUCTION_DESCRIPTION,
            authority_id="UPD-SHT-001",
            revision=1,
            fingerprint=fingerprint,
            approved=True,
            approved_by="human-reviewer",
        ),
        capabilities=(ProductionCapability.VIDEO_GENERATION,),
        expected_outputs=("video/shot",),
        state=ProductionTaskState.READY,
    )


def test_governed_reference_store_uses_production_authority_path(tmp_path: Path) -> None:
    store = PersistedGovernedReferencePlanSource(_Projects(tmp_path))  # type: ignore[arg-type]
    plan = {"schema_version": "1.0", "target": {}, "references": []}

    store.save_reference_plan("EP-001-SCN-001-SHT-001", plan)

    assert store.store_file == tmp_path / "production" / "governed_reference_plans.json"
    assert store.store_file.is_file()
    assert not (tmp_path / "story" / "acpp").exists()
    assert store.reference_plan_for_shot("ep-001-scn-001-sht-001") == plan


def test_legacy_migration_corrects_roles_without_promoting_provider_readiness(
    tmp_path: Path,
) -> None:
    store = PersistedGovernedReferencePlanSource(_Projects(tmp_path))  # type: ignore[arg-type]
    service = GovernedReferencePlanPersistenceService(
        ProviderReadyReferenceResolver(_Catalog()),
        store,
    )
    legacy = {
        "schema_version": "1.1",
        "identity_references": [
            {
                "asset_id": "CAP-CHR-001",
                "image": "D:/legacy/james.png",
                "reference_fingerprint": "james-fingerprint",
                "file_checksum": "james-checksum",
            },
            {
                "asset_id": "CAP-CHR-003",
                "image": "D:/legacy/sandra.png",
                "reference_fingerprint": "sandra-fingerprint",
                "file_checksum": "sandra-checksum",
            },
        ],
        "metadata_assets": [
            {
                "asset_id": "CAP-PLN-002",
                "category": "planet",
                "image": "D:/legacy/xorix.png",
                "reference_fingerprint": "xorix-fingerprint",
                "file_checksum": "xorix-checksum",
            }
        ],
    }

    resolution = service.migrate_legacy_reference_plan(
        shot_id="EP-001-SCN-001-SHT-001",
        target=ReferenceTarget(
            width=1280,
            height=720,
            profile_id="production-video-16x9",
            provider_id="ltx23-local",
        ),
        legacy_plan=legacy,
    )

    assert not resolution.passed
    assert [item.role for item in resolution.plan.references] == [
        ReferenceRole.PRIMARY_IDENTITY,
        ReferenceRole.SECONDARY_IDENTITY,
        ReferenceRole.ENVIRONMENT_REFERENCE,
    ]
    assert all(not item.provider_ready for item in resolution.plan.references)
    persisted = store.reference_plan_for_shot("EP-001-SCN-001-SHT-001")
    assert persisted is not None
    assert persisted["status"] == "failed"
    assert any(item["code"] == "REFERENCE_NOT_PROVIDER_READY" for item in persisted["diagnostics"])


def test_persisted_governed_plan_reaches_upd_and_xpc(tmp_path: Path) -> None:
    image = tmp_path / "references" / "james-provider-ready.png"
    _png(image)
    reference = _reference(image)
    store = PersistedGovernedReferencePlanSource(_Projects(tmp_path))  # type: ignore[arg-type]
    service = GovernedReferencePlanPersistenceService(
        ProviderReadyReferenceResolver(_Catalog((reference,))),
        store,
    )
    resolution = service.resolve_and_persist(
        shot_id="EP-001-SCN-001-SHT-001",
        target=ReferenceTarget(
            width=1280,
            height=720,
            profile_id="production-video-16x9",
            provider_id="ltx23-local",
        ),
        requests=(
            ReferenceRoleRequest(
                role=ReferenceRole.PRIMARY_IDENTITY,
                priority=ReferencePriority.REQUIRED,
                asset_id="CAP-CHR-001",
            ),
        ),
        provenance={"source": "phase-20.18.2-test"},
    )
    assert resolution.passed

    description = {
        "current_shot_id": "EP-001-SCN-001-SHT-001",
        "universal_text": "Commander James Spence holds position on the bridge.",
        "story_context": {},
        "shot": {},
        "action_performance": {},
        "assets": [],
        "camera": {},
        "lighting": {},
        "environment": {},
        "continuity": {},
        "style": {},
        "dialogue": [],
        "effects": [],
        "canonical_references": [],
        "consistency_findings": [],
        "source_policy": "approved-production-authority-only",
        "provider_neutral": True,
        "reference_plan": store.reference_plan_for_shot("EP-001-SCN-001-SHT-001"),
    }
    compiled_upd = UniversalProductionDescriptionCompilerService._compile_description(description)
    production = compiled_upd["production"]
    assert production["reference_plan"]["references"][0]["role"] == "primary_identity"

    source = _source(compiled_upd)
    compiled = ProductionPackageCompilerService(reference_root=tmp_path).compile(
        _task(source),
        source,
    )

    assert compiled.reference_plan is not None
    assert compiled.reference_plan["status"] == "passed"
    assert compiled.reference_plan["references"][0]["reference_id"] == reference.reference_id
    assert compiled.composition_plan["reference_plan"] == compiled.reference_plan
