"""Tests for Phase 17.3 ACPP creation, persistence and versioning."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from vscs.application.acpp import ACPPEditorService
from vscs.application.projects import ProjectService
from vscs.application.shots import ProductionShot
from vscs.application.ssie import Scene
from vscs.application.story import StoryService
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.yaml",
        plugin_root=tmp_path / "plugins",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _scene() -> Scene:
    return Scene(
        scene_id="EP-001-SCN-001",
        episode_id="EP-001",
        sequence_number=1,
        heading="INT. MAURITANIA BRIDGE - NIGHT",
        location_asset_id="LOC-BRIDGE",
        summary="The bridge crew studies an impossible signal.",
        participant_asset_ids=("CHR-JAMES",),
        required_asset_ids=("PROP-CONSOLE",),
    )


def _shot() -> ProductionShot:
    return ProductionShot(
        shot_id="EP-001-SCN-001-SHT-001",
        scene_id="EP-001-SCN-001",
        sequence_number=1,
        title="Bridge establishing",
        description="Wide establishing view of the active bridge.",
        estimated_duration_seconds=8.0,
        blocking_notes="James stands at the command rail.",
        dialogue_lines=("That signal should not be there.",),
    )


def test_acpp_service_prefills_package_from_shot(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    context.services.require(StoryService).save_scene(_scene())
    service = context.services.require(ACPPEditorService)

    package = service.create_from_shot(_shot())

    assert package.identity.clip_id == "EP-001-SC001-SH001-CL001"
    assert package.identity.shot_id == _shot().shot_id
    assert package.render.frame_count == 192
    assert package.prompt.positive_visual_intent == _shot().description
    assert package.audio.dialogue_lines == _shot().dialogue_lines
    assert {binding.asset_id for binding in package.assets} == {
        "LOC-BRIDGE",
        "CHR-JAMES",
        "PROP-CONSOLE",
    }
    assert service.validate(package).passed
    context.shutdown()


def test_acpp_service_persists_and_versions_packages(tmp_path: Path) -> None:
    context = build_application_context(_options(tmp_path))
    context.services.require(ProjectService).create(tmp_path / "Demo", name="Demo")
    context.services.require(StoryService).save_scene(_scene())
    service = context.services.require(ACPPEditorService)
    first = service.save(service.create_from_shot(_shot()))
    revised = replace(
        first,
        prompt=replace(
            first.prompt,
            positive_visual_intent="Revised bridge establishing view.",
        ),
    )
    second = service.save(revised)

    assert first.metadata["editor_version"] == "1"
    assert second.metadata["editor_version"] == "2"
    assert service.package(first.identity.clip_id) == second
    versions = service.versions(first.identity.clip_id)
    assert [item.metadata["editor_version"] for item in versions] == ["1", "2"]
    assert service.package_path(first.identity.clip_id).is_file()
    context.shutdown()
