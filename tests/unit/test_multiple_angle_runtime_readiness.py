"""Issue #61 B.2E: non-executable governed multiple-angle runtime readiness."""

from pathlib import Path

import pytest

from vscs.application.assets import AssetService
from vscs.application.assets.canonical_creation import CanonicalAssetCreationService
from vscs.application.caps import CanonicalReferenceService, CAPService, ReferenceLibraryService
from vscs.application.caps.derived_reference_generation import (
    DerivedReferenceGenerationError,
    DerivedReferenceGenerationService,
    DerivedReferenceGeneratorRegistry,
)
from vscs.application.caps.multiple_angle_runtime_readiness import (
    plan_multiple_angle_runtime,
)
from vscs.application.projects import ProjectService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context
from vscs.domain.assets import AssetCategory, AssetCreate
from vscs.domain.caps import CanonicalReferenceView


def _prepare(tmp_path: Path):
    context = build_application_context(
        BootstrapOptions(
            mode=StartupMode.TEST,
            config_path=tmp_path / "settings.yaml",
            plugin_root=tmp_path / "plugins",
            configure_logging=False,
            discover_plugins=False,
            load_plugins=False,
            validate_environment=False,
        )
    )
    project = tmp_path / "Project"
    context.services.require(ProjectService).create(project, name="Runtime Readiness")
    (project / "master.png").write_bytes(b"approved master fixture")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    refs = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(refs)
    CanonicalAssetCreationService(assets, caps, refs, library).create(
        AssetCreate(asset_id="CAP-PRP-999", name="Console", category=AssetCategory.PROP),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )
    service = DerivedReferenceGenerationService(refs, library, DerivedReferenceGeneratorRegistry())
    return context, project, service


def test_planned_binding_is_scoped_unique_and_never_written(tmp_path: Path) -> None:
    context, project, service = _prepare(tmp_path)
    original = (project / "master.png").read_bytes()
    qualification_id = "a" * 32
    report = plan_multiple_angle_runtime(
        service,
        "CAP-PRP-999",
        CanonicalReferenceView.FRONT,
        seed=1,
        qualification_id=qualification_id,
    )
    assert report.qualification_id == qualification_id
    assert report.master_reference_id
    assert report.master_sha256
    assert report.queue_path.is_relative_to(project)
    assert report.output_path.is_relative_to(project)
    assert report.proposed_graph["1"]["inputs"]["queue_file"] == str(report.queue_path)
    assert report.proposed_queue["jobs"][0]["master_sha256"] == report.master_sha256
    assert report.proposed_queue["jobs"][0]["reference_inputs"] == [str(project / "master.png")]
    assert report.blockers
    assert not report.generation_authorized
    assert not report.queue_path.exists()
    assert not report.output_path.exists()
    assert not (project / ".vscs" / "runtime").exists()
    assert (project / "master.png").read_bytes() == original
    context.shutdown()


def test_collision_is_rejected_without_overwrite(tmp_path: Path) -> None:
    context, project, service = _prepare(tmp_path)
    qualification_id = "b" * 32
    queue = project / ".vscs" / "runtime" / "comfyui" / "queues"
    queue.mkdir(parents=True)
    existing = queue / f"multiple_angle_{qualification_id}.json"
    existing.write_text("protected history", encoding="utf-8")
    with pytest.raises(DerivedReferenceGenerationError, match="collision"):
        plan_multiple_angle_runtime(
            service,
            "CAP-PRP-999",
            CanonicalReferenceView.FRONT,
            seed=1,
            qualification_id=qualification_id,
        )
    assert existing.read_text(encoding="utf-8") == "protected history"
    context.shutdown()


def test_bad_staging_identifiers_fail_closed(tmp_path: Path) -> None:
    context, _project, service = _prepare(tmp_path)
    for identifier in ("../escape", "A" * 32, "", "a" * 31):
        with pytest.raises(DerivedReferenceGenerationError, match="Qualification ID"):
            plan_multiple_angle_runtime(
                service,
                "CAP-PRP-999",
                CanonicalReferenceView.FRONT,
                seed=1,
                qualification_id=identifier,
            )
    context.shutdown()


def test_missing_master_rejects_readiness(tmp_path: Path) -> None:
    context, project, service = _prepare(tmp_path)
    (project / "master.png").unlink()  # Disposable test fixture only.
    with pytest.raises(DerivedReferenceGenerationError, match="does not exist"):
        plan_multiple_angle_runtime(
            service,
            "CAP-PRP-999",
            CanonicalReferenceView.FRONT,
            seed=1,
        )
    context.shutdown()


def test_master_change_during_compilation_aborts(tmp_path: Path, monkeypatch) -> None:
    context, project, service = _prepare(tmp_path)
    original_resolver = service._resolve_locked_master
    calls = 0

    def resolve_with_change(asset_id: str):
        nonlocal calls
        calls += 1
        if calls == 3:
            (project / "master.png").write_bytes(b"changed disposable fixture")
        return original_resolver(asset_id)

    monkeypatch.setattr(service, "_resolve_locked_master", resolve_with_change)
    with pytest.raises(DerivedReferenceGenerationError, match="MASTER changed"):
        plan_multiple_angle_runtime(
            service,
            "CAP-PRP-999",
            CanonicalReferenceView.FRONT,
            seed=1,
        )
    assert calls == 3
    assert not (project / ".vscs" / "runtime").exists()
    context.shutdown()


def test_existing_output_file_is_preserved(tmp_path: Path) -> None:
    context, project, service = _prepare(tmp_path)
    qualification_id = "c" * 32
    destination = (
        project
        / "Canonical Assets"
        / "CAP-PRP-999"
        / "Images"
        / "Derived"
        / f"front_qualification_{qualification_id}.png"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"historical test candidate")
    with pytest.raises(DerivedReferenceGenerationError, match="collision"):
        plan_multiple_angle_runtime(
            service,
            "CAP-PRP-999",
            CanonicalReferenceView.FRONT,
            seed=1,
            qualification_id=qualification_id,
        )
    assert destination.read_bytes() == b"historical test candidate"
    context.shutdown()
