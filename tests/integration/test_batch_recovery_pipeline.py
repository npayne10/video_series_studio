"""Integration coverage for persistent batch resume and recovery."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    BatchRecoveryService,
    PromptGraphBuildContext,
    PromptGraphResolver,
    PromptGraphSource,
    PromptNodeKind,
)
from vscs.application.rendering import QualityLevel, RendererKind
from vscs.bootstrap import BootstrapOptions, StartupMode, build_application_context


def _options(path: Path) -> BootstrapOptions:
    return BootstrapOptions(
        mode=StartupMode.TEST,
        config_path=path,
        configure_logging=False,
        discover_plugins=False,
        load_plugins=False,
        validate_environment=False,
    )


def _item(item_id: str, shot_id: str) -> BatchCompilationItem:
    return BatchCompilationItem(
        item_id,
        PromptGraphBuildContext(
            graph_id=f"GRAPH-{shot_id}",
            production_id="XORIX",
            container_id="EP-001",
            scene_id="SCN-001",
            shot_id=shot_id,
            renderer=RendererKind.COMFYUI,
            quality_level=QualityLevel.PREVIEW,
            workflow_id="ltx23_preview_v1",
        ),
        require_production_ready=False,
    )


def _sources() -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            "intent",
            PromptNodeKind.VISUAL_INTENT,
            "Intent",
            "The Iron Horizon approaches Xorix with blue-white engine trails.",
            mandatory=True,
            sequence=1,
        ),
        PromptGraphSource(
            "camera",
            PromptNodeKind.CAMERA,
            "Camera",
            "Wide restrained tracking shot.",
            mandatory=True,
            sequence=2,
        ),
        PromptGraphSource(
            "lighting",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural reflected planetary light.",
            mandatory=True,
            sequence=3,
        ),
        PromptGraphSource(
            "renderer",
            PromptNodeKind.RENDERER,
            "Renderer",
            "Renderer-neutral cinematic intent.",
            mandatory=True,
            sequence=4,
        ),
        PromptGraphSource(
            "quality",
            PromptNodeKind.QUALITY,
            "Quality",
            "Stable Preview quality at 24 fps.",
            mandatory=True,
            sequence=5,
        ),
    )


def test_restart_restores_only_unfinished_shot(tmp_path: Path) -> None:
    settings = tmp_path / "settings.toml"
    request = BatchCompilationRequest.create(
        "BATCH-RECOVERY",
        (_item("ITEM-001", "SHT-001"), _item("ITEM-002", "SHT-002")),
    )

    first = build_application_context(_options(settings))
    try:
        recovery = first.services.require(BatchRecoveryService)
        recovery.begin(request)
        recovery.record_result(
            request.batch_id,
            BatchCompilationItemResult(
                "ITEM-001",
                "SHT-001",
                BatchCompilationItemStatus.COMPLETED,
            ),
        )
    finally:
        first.shutdown()

    second = build_application_context(_options(settings))
    try:
        second.services.require(PromptGraphResolver).register("SHT-002", _sources())
        scheduler = second.services.require(BatchCompilationScheduler)

        restored = scheduler.restore_pending()
        finished = scheduler.run_next()

        assert tuple(item.item_id for item in restored[0].request.items) == ("ITEM-002",)
        assert finished is not None
        assert tuple(result.item_id for result in finished.job.results) == ("ITEM-002",)
        assert second.services.require(BatchRecoveryService).pending_checkpoints() == ()
    finally:
        second.shutdown()
