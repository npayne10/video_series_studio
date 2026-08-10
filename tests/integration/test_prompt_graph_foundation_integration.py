"""Phase 17.4.1 end-to-end prompt graph foundation coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from vscs.application.prompt_graph import (
    PromptGraphBuildContext,
    PromptGraphBuilder,
    PromptGraphChangeArea,
    PromptGraphCompilationError,
    PromptGraphCompiler,
    PromptGraphDiffer,
    PromptGraphResolver,
    PromptGraphResourceInventory,
    PromptGraphSnapshotService,
    PromptGraphSource,
    PromptGraphValidator,
    PromptNodeKind,
    PromptSectionKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(tmp_path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=tmp_path / "settings.toml",
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _context() -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        graph_id="GRAPH-XORIX-EP001-SCN004-SHT015",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-004",
        shot_id="SHT-015",
        clip_id="CLP-001",
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PRODUCTION,
        workflow_id="ltx23_production_v1",
    )


def _inventory() -> PromptGraphResourceInventory:
    return PromptGraphResourceInventory(
        canonical_asset_ids=frozenset(
            {
                "CAP-CHR-JAMES-SPENCE",
                "CAP-SHP-IRON-HORIZON",
                "CAP-LOC-IRON-HORIZON-BRIDGE",
            }
        ),
        reference_ids=frozenset(
            {
                "REF-CHR-JAMES-SPENCE-01",
                "REF-SHP-IRON-HORIZON-01",
                "REF-LOC-IRON-HORIZON-BRIDGE-01",
            }
        ),
    )


def _sources(*, revised: bool = False) -> tuple[PromptGraphSource, ...]:
    continuity = (
        "Maintain James at the forward command rail, preserve the bridge lighting, "
        "and retain the Iron Horizon's blue-white engine state from the prior shot."
        if revised
        else "Maintain James at the forward command rail and preserve bridge lighting."
    )
    dialogue = (
        "James says, 'Take us down to the starport.'" if revised else "James says, 'Begin descent.'"
    )
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Visual intent",
            "A disciplined orbital descent establishes Xorix as a real inhabited world.",
            mandatory=True,
            sequence=1,
        ),
        PromptGraphSource(
            "location",
            PromptNodeKind.LOCATION,
            "Iron Horizon bridge",
            "A compact functional Guild bridge with restrained interfaces and clear sightlines.",
            canonical_asset_id="CAP-LOC-IRON-HORIZON-BRIDGE",
            reference_ids=("REF-LOC-IRON-HORIZON-BRIDGE-01",),
            mandatory=True,
            sequence=2,
        ),
        PromptGraphSource(
            "ship",
            PromptNodeKind.SHIP,
            "Iron Horizon",
            "The 145 metre Guild survey spacecraft has four rear fusion engines "
            "producing controlled blue-white engine trails.",
            canonical_asset_id="CAP-SHP-IRON-HORIZON",
            reference_ids=("REF-SHP-IRON-HORIZON-01",),
            mandatory=True,
            sequence=3,
        ),
        PromptGraphSource(
            "james",
            PromptNodeKind.CHARACTER,
            "Commander James Spence",
            "Commander James Spence, age 43, wears the approved Guild command "
            "uniform and remains calm and focused.",
            canonical_asset_id="CAP-CHR-JAMES-SPENCE",
            reference_ids=("REF-CHR-JAMES-SPENCE-01",),
            mandatory=True,
            sequence=4,
        ),
        PromptGraphSource(
            "camera",
            PromptNodeKind.CAMERA,
            "Camera",
            "A restrained 35 mm tracking move follows James toward the forward rail.",
            mandatory=True,
            sequence=5,
        ),
        PromptGraphSource(
            "lighting",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural planetary light enters through the bridge viewport with "
            "subtle instrument fill.",
            mandatory=True,
            sequence=6,
        ),
        PromptGraphSource(
            "continuity",
            PromptNodeKind.CONTINUITY,
            "Continuity",
            continuity,
            mandatory=True,
            sequence=7,
        ),
        PromptGraphSource(
            "dialogue",
            PromptNodeKind.DIALOGUE,
            "James dialogue",
            dialogue,
            mandatory=True,
            sequence=8,
        ),
        PromptGraphSource(
            "renderer",
            PromptNodeKind.RENDERER,
            "Renderer",
            "Renderer-neutral cinematic video intent for the selected ComfyUI workflow.",
            mandatory=True,
            sequence=9,
        ),
        PromptGraphSource(
            "quality",
            PromptNodeKind.QUALITY,
            "Quality",
            "Production quality at 24 fps with stable temporal detail and consistent geometry.",
            mandatory=True,
            sequence=10,
        ),
        PromptGraphSource(
            "restriction",
            PromptNodeKind.RESTRICTION,
            "Restrictions",
            "No uniform changes, no altered hull geometry and no missing engine trails.",
            sequence=11,
        ),
        PromptGraphSource(
            "negative",
            PromptNodeKind.NEGATIVE,
            "Negative prompt",
            "No fantasy glow, excessive holograms, visual clutter or uncontrolled camera motion.",
            sequence=12,
        ),
    )


def test_complete_prompt_graph_foundation_pipeline(tmp_path: Path) -> None:
    application = build_application_context(_options(tmp_path))
    try:
        resolver = application.services.require(PromptGraphResolver)
        builder = application.services.require(PromptGraphBuilder)
        validator = application.services.require(PromptGraphValidator)
        compiler = application.services.require(PromptGraphCompiler)
        snapshots = application.services.require(PromptGraphSnapshotService)

        resolver.register("SHT-015", _sources())
        first_build = builder.build(_context())
        repeated_build = builder.build(_context())
        validation = validator.validate(first_build.graph, _inventory())
        package = compiler.compile(first_build.graph, _inventory())
        snapshot = snapshots.capture(first_build.graph, snapshot_id="SNAP-001")

        assert first_build.report.passed
        assert first_build.graph.to_dict() == repeated_build.graph.to_dict()
        assert validation.passed
        assert validation.completeness.production_ready
        assert package.provenance.graph_checksum == snapshot.checksum
        assert package.canonical_asset_ids == (
            "CAP-CHR-JAMES-SPENCE",
            "CAP-LOC-IRON-HORIZON-BRIDGE",
            "CAP-SHP-IRON-HORIZON",
        )
        assert "controlled blue-white engine trails" in package.positive_prompt
        assert "Begin descent" in package.positive_prompt
        assert "No uniform changes" in package.negative_prompt
        assert "No fantasy glow" in package.negative_prompt
        assert package.section(PromptSectionKind.CONTINUITY) is not None
        assert package.section(PromptSectionKind.DIALOGUE) is not None
        assert snapshots.latest(first_build.graph.metadata.graph_id) == snapshot
    finally:
        application.shutdown()


def test_snapshot_and_prompt_diffs_expose_continuity_and_dialogue_changes(
    tmp_path: Path,
) -> None:
    application = build_application_context(_options(tmp_path))
    try:
        resolver = application.services.require(PromptGraphResolver)
        builder = application.services.require(PromptGraphBuilder)
        compiler = application.services.require(PromptGraphCompiler)
        snapshots = application.services.require(PromptGraphSnapshotService)
        differ = application.services.require(PromptGraphDiffer)

        resolver.register("SHT-015", _sources())
        first_graph = builder.build(_context()).graph
        first_snapshot = snapshots.capture(first_graph, snapshot_id="SNAP-001")
        first_package = compiler.compile(first_graph, _inventory())

        resolver.register("SHT-015", _sources(revised=True))
        second_graph = builder.build(_context()).graph
        second_snapshot = snapshots.capture(second_graph, snapshot_id="SNAP-002")
        second_package = compiler.compile(second_graph, _inventory())

        graph_diff = differ.compare_snapshots(first_snapshot, second_snapshot)
        package_diff = differ.compare_packages(first_package, second_package)

        assert graph_diff.changed
        assert any(
            change.area is PromptGraphChangeArea.NODE
            and change.subject == "continuity"
            and change.continuity_sensitive
            for change in graph_diff.changes
        )
        assert any(
            change.area is PromptGraphChangeArea.NODE and change.subject == "dialogue"
            for change in graph_diff.changes
        )
        assert any(
            change.area is PromptGraphChangeArea.PROMPT_SECTION
            and change.subject == PromptSectionKind.CONTINUITY.value
            and change.continuity_sensitive
            for change in package_diff.changes
        )
        assert any(
            change.area is PromptGraphChangeArea.PROMPT_SECTION
            and change.subject == PromptSectionKind.DIALOGUE.value
            for change in package_diff.changes
        )
        assert first_package.provenance.graph_checksum != second_package.provenance.graph_checksum
        assert snapshots.history(first_graph.metadata.graph_id) == (
            first_snapshot,
            second_snapshot,
        )
    finally:
        application.shutdown()


def test_invalid_canonical_inventory_blocks_compilation(tmp_path: Path) -> None:
    application = build_application_context(_options(tmp_path))
    try:
        resolver = application.services.require(PromptGraphResolver)
        builder = application.services.require(PromptGraphBuilder)
        compiler = application.services.require(PromptGraphCompiler)

        resolver.register("SHT-015", _sources())
        graph = builder.build(_context()).graph
        incomplete_inventory = PromptGraphResourceInventory(
            canonical_asset_ids=frozenset({"CAP-CHR-JAMES-SPENCE"}),
            reference_ids=_inventory().reference_ids,
        )

        with pytest.raises(
            PromptGraphCompilationError,
            match="validation issues",
        ):
            compiler.compile(graph, incomplete_inventory)
    finally:
        application.shutdown()
