"""Issue #61 B.2C offline camera binding and authority regression."""

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
from vscs.application.caps.multiple_angle_binding import (
    MultipleAngleBindingError,
    MultipleAngleOfflineCompiler,
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
    context.services.require(ProjectService).create(project, name="Offline Camera")
    (project / "master.png").write_bytes(b"synthetic approved MASTER fixture")
    assets = context.services.require(AssetService)
    caps = context.services.require(CAPService)
    refs = context.services.require(CanonicalReferenceService)
    library = ReferenceLibraryService(refs)
    CanonicalAssetCreationService(assets, caps, refs, library).create(
        AssetCreate(asset_id="CAP-PRP-999", name="Test Console", category=AssetCategory.PROP),
        Path("master.png"),
        confirmed_chatgpt_master=True,
    )
    service = DerivedReferenceGenerationService(refs, library, DerivedReferenceGeneratorRegistry())
    return context, project, service


def test_all_cardinal_views_bind_locked_master_without_io(tmp_path: Path) -> None:
    context, project, service = _prepare(tmp_path)
    compiler = MultipleAngleOfflineCompiler(service)
    before = (project / "master.png").read_bytes()
    for view, angle in (
        (CanonicalReferenceView.FRONT, 0),
        (CanonicalReferenceView.RIGHT, 90),
        (CanonicalReferenceView.REAR, 180),
        (CanonicalReferenceView.LEFT, 270),
    ):
        report = compiler.compile("CAP-PRP-999", view, seed=1)
        assert not report.generation_authorized
        assert report.camera_horizontal_degrees == angle
        assert report.compiled_graph["221"]["inputs"]["horizontal_angle"] == angle
        assert report.compiled_graph["1"]["class_type"] == "XCICQwenReferenceJobLoader"
        assert report.compiled_graph["1"]["inputs"]["queue_file"].startswith("__VSCS_")
        assert report.compiled_graph["219:160"]["inputs"]["image"] == ["1", 0]
        assert report.queue_payload["jobs"][0]["reference_inputs"] == [str(project / "master.png")]
        assert report.source_master_reference_id
        assert report.blockers
    assert (project / "master.png").read_bytes() == before
    assert not (project / ".vscs" / "runtime").exists()
    context.shutdown()


def test_invalid_view_seed_and_unavailable_node_are_fail_closed(tmp_path: Path) -> None:
    context, _project, service = _prepare(tmp_path)
    compiler = MultipleAngleOfflineCompiler(service)
    with pytest.raises(MultipleAngleBindingError, match="Only Front"):
        compiler.compile("CAP-PRP-999", CanonicalReferenceView.TOP, seed=1)
    with pytest.raises(MultipleAngleBindingError, match="Seed"):
        compiler.compile("CAP-PRP-999", CanonicalReferenceView.FRONT, seed=-1)
    report = compiler.compile(
        "CAP-PRP-999", CanonicalReferenceView.FRONT, seed=1, object_info={"LoadImage": {}}
    )
    assert "CameraAngle" in report.missing_node_types
    assert any("model inventory" in blocker for blocker in report.blockers)
    assert not report.generation_authorized
    context.shutdown()


def test_read_only_model_inventory_fails_closed_on_missing_files(tmp_path: Path) -> None:
    context, _project, service = _prepare(tmp_path)
    model_root = tmp_path / "models"
    model_root.mkdir()
    compiler = MultipleAngleOfflineCompiler(service)
    report = compiler.compile(
        "CAP-PRP-999",
        CanonicalReferenceView.FRONT,
        seed=1,
        model_root=model_root,
    )
    assert len(report.missing_model_files) == 5
    assert any("missing or empty" in blocker for blocker in report.blockers)
    assert not report.generation_authorized
    context.shutdown()


def test_missing_master_authority_blocks_compilation(tmp_path: Path) -> None:
    context, project, service = _prepare(tmp_path)
    (project / "master.png").unlink()  # Disposable fixture only.
    with pytest.raises(DerivedReferenceGenerationError, match="does not exist"):
        MultipleAngleOfflineCompiler(service).compile(
            "CAP-PRP-999", CanonicalReferenceView.FRONT, seed=1
        )
    context.shutdown()


def test_template_source_tampering_is_rejected(tmp_path: Path) -> None:
    context, _project, service = _prepare(tmp_path)
    template_path = MultipleAngleOfflineCompiler(service).template_path
    tampered = tmp_path / "unreviewed.json"
    tampered.write_text(
        template_path.read_text(encoding="utf-8").replace(
            "__VSCS_PENDING_MASTER_BINDING__", "cyber_genesis.png"
        ),
        encoding="utf-8",
    )
    with pytest.raises(MultipleAngleBindingError, match="source marker"):
        MultipleAngleOfflineCompiler(service, template_path=tampered).compile(
            "CAP-PRP-999", CanonicalReferenceView.FRONT, seed=1
        )
    context.shutdown()


def test_reviewed_template_accepts_windows_crlf_but_rejects_changed_content(tmp_path: Path) -> None:
    context, _project, service = _prepare(tmp_path)
    compiler = MultipleAngleOfflineCompiler(service)
    original_bytes = compiler.template_path.read_bytes()
    assert b"\r\n" not in original_bytes
    windows_path = tmp_path / compiler.TEMPLATE_NAME
    windows_path.write_bytes(original_bytes.replace(b"\n", b"\r\n"))

    windows_report = MultipleAngleOfflineCompiler(
        service, template_path=windows_path
    ).compile("CAP-PRP-999", CanonicalReferenceView.FRONT, seed=1)
    assert windows_report.template_sha256 == compiler.EXPECTED_TEMPLATE_SHA256
    assert not windows_report.generation_authorized

    windows_path.write_bytes(
        windows_path.read_bytes().replace(
            b"__VSCS_PENDING_MASTER_BINDING__", b"__VSCS_PENDING_MASTER_BINDING_TAMPERED__"
        )
    )
    with pytest.raises(MultipleAngleBindingError, match="template hash changed"):
        MultipleAngleOfflineCompiler(service, template_path=windows_path).compile(
            "CAP-PRP-999", CanonicalReferenceView.FRONT, seed=1
        )
    context.shutdown()
