"""Issue #61 B.2F offline staging is never a GPU submission."""

import json
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
from vscs.application.caps.multiple_angle_execution_guard import (
    cancel_offline_qualification,
    inspect_offline_qualification,
    stage_offline_qualification,
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
    context.services.require(ProjectService).create(project, name="Offline Stage")
    (project / "master.png").write_bytes(b"approved synthetic MASTER")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    references = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(references)
    CanonicalAssetCreationService(assets, caps, references, library).create(
        AssetCreate(asset_id="CAP-PRP-999", name="Console", category=AssetCategory.PROP),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )
    service = DerivedReferenceGenerationService(
        references, library, DerivedReferenceGeneratorRegistry()
    )
    plan = plan_multiple_angle_runtime(
        service,
        "CAP-PRP-999",
        CanonicalReferenceView.FRONT,
        seed=1,
        qualification_id="d" * 32,
    )
    return context, project, service, plan


def test_offline_staging_requires_explicit_opt_in(tmp_path: Path) -> None:
    context, project, service, plan = _prepare(tmp_path)
    with pytest.raises(DerivedReferenceGenerationError, match="consent"):
        stage_offline_qualification(service, plan)
    assert not (project / ".vscs" / "runtime").exists()
    context.shutdown()


def test_offline_staging_and_restart_inspection_preserve_master(tmp_path: Path) -> None:
    context, project, service, plan = _prepare(tmp_path)
    before = (project / "master.png").read_bytes()
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    assert staged.queue_path.is_file()
    assert staged.manifest_path.is_file()
    assert staged.reservation_path.is_file()
    assert not staged.output_path.exists()
    assert not staged.generation_authorized
    assert inspect_offline_qualification(staged) == ("staged_offline_unsubmitted", ())
    assert (project / "master.png").read_bytes() == before
    context.shutdown()


def test_detailed_mode_is_persisted_and_guarded_before_submission(tmp_path: Path) -> None:
    context, _project, service, _plan = _prepare(tmp_path)
    plan = plan_multiple_angle_runtime(
        service,
        "CAP-PRP-999",
        CanonicalReferenceView.REAR,
        seed=11,
        sampling_mode="detailed",
        qualification_id="f" * 32,
    )
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    assert staged.sampling_mode == "detailed"
    assert json.loads(staged.manifest_path.read_text())["sampling_mode"] == "detailed"
    assert inspect_offline_qualification(staged) == ("staged_offline_unsubmitted", ())
    context.shutdown()


def test_collision_rejects_repeated_staging_without_overwrite(tmp_path: Path) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    before = staged.queue_path.read_bytes()
    with pytest.raises(DerivedReferenceGenerationError, match="collision"):
        stage_offline_qualification(service, plan, allow_offline_staging=True)
    assert staged.queue_path.read_bytes() == before
    context.shutdown()


def test_queue_tampering_is_detected_without_reconciliation(tmp_path: Path) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    staged.queue_path.write_text("tampered", encoding="utf-8")
    status, errors = inspect_offline_qualification(staged)
    assert status == "invalid"
    assert errors
    assert not staged.output_path.exists()
    context.shutdown()


def test_cancellation_is_append_only_and_idempotence_fails_closed(tmp_path: Path) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    old_queue = staged.queue_path.read_bytes()
    cancellation = cancel_offline_qualification(staged)
    assert cancellation.is_file()
    assert inspect_offline_qualification(staged) == ("cancelled", ())
    assert staged.queue_path.read_bytes() == old_queue
    with pytest.raises(DerivedReferenceGenerationError, match="cancelled safely"):
        cancel_offline_qualification(staged)
    context.shutdown()


def test_stale_master_blocks_staging_before_disk_changes(tmp_path: Path) -> None:
    context, project, service, plan = _prepare(tmp_path)
    (project / "master.png").write_bytes(b"changed synthetic fixture")
    with pytest.raises(DerivedReferenceGenerationError, match="MASTER image changed"):
        stage_offline_qualification(service, plan, allow_offline_staging=True)
    assert not (project / ".vscs" / "runtime").exists()
    context.shutdown()


def test_unreconciled_output_is_not_accepted(tmp_path: Path) -> None:
    context, _project, service, plan = _prepare(tmp_path)
    staged = stage_offline_qualification(service, plan, allow_offline_staging=True)
    staged.output_path.parent.mkdir(parents=True, exist_ok=True)
    staged.output_path.write_bytes(b"untrusted output")
    status, errors = inspect_offline_qualification(staged)
    assert status == "invalid"
    assert any("reconciliation" in error for error in errors)
    context.shutdown()
