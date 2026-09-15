from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vscs.application.governed_reference_plan_source import (
    PersistedGovernedReferencePlanSource,
)
from vscs.application.governed_reference_suitability import (
    GovernedReferenceSuitabilityError,
    GovernedReferenceSuitabilityService,
)
from vscs.application.production_package import (
    ProductionPackage,
    ProductionPackageProvenance,
    ProductionPackageStatus,
)
from vscs.application.reference_preparing_universal_compiler import (
    GovernedReferenceAwareUniversalProductionDescriptionCompilerService,
)
from vscs.application.universal_production_description_compiler import (
    UniversalProductionDescriptionCompilerError,
)


class _Projects:
    def __init__(self, root: Path) -> None:
        self.project_directory = root


class _Packages:
    def __init__(self, package: ProductionPackage) -> None:
        self.value = package

    def current_package(self, _shot_id: str):
        return self.value

    def materialize(self, _shot_id: str):
        return self.value

    def require_current_package(self, _shot_id: str):
        return self.value


def _package(*, with_references: bool = True) -> ProductionPackage:
    references = (
        (
            {
                "asset_id": "CAP-CHR-001",
                "canonical_reference": "assets/characters/james.png",
            },
        )
        if with_references
        else ()
    )
    assets = (
        {
            "production": {
                "asset_id": "CAP-CHR-001",
                "category": "character",
                "canonical_reference": "assets/characters/james.png",
                "role": "Dialogue Speaker",
            }
        },
    )
    return ProductionPackage(
        package_id="PP-SHT-001",
        shot_id="EP-001-SCN-001-SHT-001",
        schema_version="1.0",
        source_fingerprint="source",
        package_fingerprint="package",
        provenance=ProductionPackageProvenance("PIP", "source", "PRV", "review"),
        story_context={"scene": "Bridge"},
        shot={"title": "Bridge Dialogue"},
        assets=assets,
        camera={"production": {"shot_size": "medium", "movement": "static"}},
        lighting={"production": {"lighting_intent": "practical_motivated"}},
        environment={"environment_context": "interior", "atmosphere_state": "controlled"},
        action_performance={
            "production": {
                "temporal_narrative": "James remains at the bridge console.",
                "spoken_content": 'James: "Status report."',
            }
        },
        continuity={"production": {}},
        style={"production": {"provider_neutral": True}},
        dialogue=({"speaker": "James", "text": "Status report."},),
        effects=(),
        references=references,
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


def _write_suitability(
    root: Path,
    reference_file: Path,
    *,
    shot_id: str = "EP-001-SCN-001-SHT-001",
    provider_ready: bool = True,
    checksum: str | None = None,
) -> Path:
    reference_file.parent.mkdir(parents=True, exist_ok=True)
    if not reference_file.exists():
        reference_file.write_bytes(b"explicit-provider-ready-reference")
    file_checksum = checksum or hashlib.sha256(reference_file.read_bytes()).hexdigest()
    payload = {
        "schema_version": "1.0",
        "shot_id": shot_id,
        "target": {
            "width": 1280,
            "height": 720,
            "profile_id": "production-video-16x9",
            "provider_id": "ltx23-local",
        },
        "references": [
            {
                "reference_id": "LIVE-PRIMARY-CAP-CHR-001",
                "asset_id": "CAP-CHR-001",
                "role": "primary_identity",
                "reference_class": "provider_ready_derivative",
                "subject_type": "character",
                "source_path": str(reference_file),
                "canonical_source_id": "CAP-CHR-001",
                "label": "James provider-ready identity",
                "width": 1280,
                "height": 720,
                "file_checksum": file_checksum,
                "provider_ready": provider_ready,
                "provider_profiles": ["production-video-16x9"],
                "coverage": {
                    "framing_type": "full_body",
                    "coverage": "full_required_asset",
                    "required_features_visible": True,
                    "identity_visible": True,
                    "full_required_asset_visible": True,
                },
            }
        ],
    }
    path = (
        root
        / "production"
        / f"governed_reference_suitability_{shot_id.upper()}.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def test_explicit_suitability_defaults_priority_to_required_and_persists(
    tmp_path: Path,
) -> None:
    package = _package()
    reference_file = tmp_path / "references" / "james.bin"
    _write_suitability(tmp_path, reference_file)
    projects = _Projects(tmp_path)
    service = GovernedReferenceSuitabilityService(projects)  # type: ignore[arg-type]

    plan = service.ensure_for_package(package)

    assert plan is not None
    assert plan["status"] == "passed"
    assert plan["references"][0]["priority"] == "required"
    store = PersistedGovernedReferencePlanSource(projects)  # type: ignore[arg-type]
    persisted = store.reference_plan_for_shot(package.shot_id)
    assert persisted is not None
    assert persisted["references"][0]["reference_id"] == "LIVE-PRIMARY-CAP-CHR-001"


def test_missing_explicit_suitability_never_promotes_canonical_reference(
    tmp_path: Path,
) -> None:
    package = _package()
    service = GovernedReferenceSuitabilityService(_Projects(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(
        GovernedReferenceSuitabilityError,
        match="Explicit provider-ready suitability authority is required",
    ):
        service.ensure_for_package(package)

    assert not (tmp_path / "production" / "governed_reference_plans.json").exists()


def test_failed_explicit_review_is_persisted_and_blocks(tmp_path: Path) -> None:
    package = _package()
    reference_file = tmp_path / "references" / "james.bin"
    _write_suitability(tmp_path, reference_file, provider_ready=False)
    projects = _Projects(tmp_path)
    service = GovernedReferenceSuitabilityService(projects)  # type: ignore[arg-type]

    with pytest.raises(
        GovernedReferenceSuitabilityError,
        match="REFERENCE_NOT_PROVIDER_READY",
    ):
        service.ensure_for_package(package)

    store = PersistedGovernedReferencePlanSource(projects)  # type: ignore[arg-type]
    persisted = store.reference_plan_for_shot(package.shot_id)
    assert persisted is not None
    assert persisted["status"] == "failed"


def test_reference_free_package_requires_no_suitability(tmp_path: Path) -> None:
    service = GovernedReferenceSuitabilityService(_Projects(tmp_path))  # type: ignore[arg-type]

    assert service.ensure_for_package(_package(with_references=False)) is None


def test_suitability_shot_mismatch_is_rejected(tmp_path: Path) -> None:
    package = _package()
    reference_file = tmp_path / "references" / "james.bin"
    path = _write_suitability(tmp_path, reference_file)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["shot_id"] = "EP-999-SCN-999-SHT-999"
    path.write_text(json.dumps(raw), encoding="utf-8")
    service = GovernedReferenceSuitabilityService(_Projects(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(GovernedReferenceSuitabilityError, match="Shot ID mismatch"):
        service.ensure_for_package(package)


def test_suitability_checksum_mismatch_is_rejected(tmp_path: Path) -> None:
    package = _package()
    reference_file = tmp_path / "references" / "james.bin"
    _write_suitability(tmp_path, reference_file, checksum="0" * 64)
    service = GovernedReferenceSuitabilityService(_Projects(tmp_path))  # type: ignore[arg-type]

    with pytest.raises(GovernedReferenceSuitabilityError, match="file checksum"):
        service.ensure_for_package(package)


def test_live_upd_create_blocks_before_draft_when_suitability_is_missing(
    tmp_path: Path,
) -> None:
    package = _package()
    projects = _Projects(tmp_path)
    service = GovernedReferenceAwareUniversalProductionDescriptionCompilerService(
        projects,  # type: ignore[arg-type]
        _Packages(package),  # type: ignore[arg-type]
    )

    with pytest.raises(
        UniversalProductionDescriptionCompilerError,
        match="Governed reference preparation failed",
    ):
        service.create_from_current_package(package.shot_id)

    assert not service.draft_file.exists()


def test_live_upd_create_persists_and_embeds_passing_reference_plan(
    tmp_path: Path,
) -> None:
    package = _package()
    reference_file = tmp_path / "references" / "james.bin"
    _write_suitability(tmp_path, reference_file)
    projects = _Projects(tmp_path)
    service = GovernedReferenceAwareUniversalProductionDescriptionCompilerService(
        projects,  # type: ignore[arg-type]
        _Packages(package),  # type: ignore[arg-type]
    )

    draft = service.create_from_current_package(package.shot_id)

    plan = draft.description_value()["reference_plan"]
    assert plan["status"] == "passed"
    assert plan["references"][0]["role"] == "primary_identity"
