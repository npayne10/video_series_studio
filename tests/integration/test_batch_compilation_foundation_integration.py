"""Phase 17.4.3 foundation certification for batch prompt compilation."""

from pathlib import Path

from vscs.application.prompt_graph import (
    BatchCompilationHistory,
    BatchCompilationItem,
    BatchCompilationItemResult,
    BatchCompilationItemStatus,
    BatchCompilationRequest,
    BatchCompilationScheduler,
    BatchProgressTracker,
    BatchRecoveryService,
    BatchReportingService,
    BatchStatisticsService,
    CompilationDependency,
    CompilationDependencyKind,
    IncrementalCompilationHistory,
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


def _context(shot_id: str) -> PromptGraphBuildContext:
    return PromptGraphBuildContext(
        graph_id=f"GRAPH-{shot_id}",
        production_id="XORIX",
        container_id="EP-001",
        scene_id="SCN-001",
        shot_id=shot_id,
        renderer=RendererKind.COMFYUI,
        quality_level=QualityLevel.PREVIEW,
        workflow_id="ltx23_preview_v1",
    )


def _sources(shot_id: str) -> tuple[PromptGraphSource, ...]:
    return (
        PromptGraphSource(
            f"intent-{shot_id}",
            PromptNodeKind.VISUAL_INTENT,
            "Visual intent",
            "The Iron Horizon approaches Xorix with controlled blue-white "
            "engine trails.",
            mandatory=True,
            sequence=1,
        ),
        PromptGraphSource(
            f"camera-{shot_id}",
            PromptNodeKind.CAMERA,
            "Camera",
            "Wide restrained tracking shot with stable spacecraft framing.",
            mandatory=True,
            sequence=2,
        ),
        PromptGraphSource(
            f"lighting-{shot_id}",
            PromptNodeKind.LIGHTING,
            "Lighting",
            "Natural reflected planetary light with physically plausible exposure.",
            mandatory=True,
            sequence=3,
        ),
        PromptGraphSource(
            f"renderer-{shot_id}",
            PromptNodeKind.RENDERER,
            "Renderer",
            "Renderer-neutral cinematic video intent for ComfyUI execution.",
            mandatory=True,
            sequence=4,
        ),
        PromptGraphSource(
            f"quality-{shot_id}",
            PromptNodeKind.QUALITY,
            "Quality",
            "Preview quality at 24 fps with stable temporal consistency.",
            mandatory=True,
            sequence=5,
        ),
        PromptGraphSource(
            f"restriction-{shot_id}",
            PromptNodeKind.NEGATIVE,
            "Negative constraints",
            "No fantasy glow, no extra engines, no orange engine trails.",
            sequence=6,
        ),
    )


def _item(item_id: str, shot_id: str) -> BatchCompilationItem:
    dependency = CompilationDependency(
        CompilationDependencyKind.CANONICAL_ASSET,
        "CAP-SHP-IRON-HORIZON",
        "cap-v1",
    )
    return BatchCompilationItem(
        item_id,
        _context(shot_id),
        sequence=int(shot_id.rsplit("-", 1)[-1]),
        require_production_ready=False,
        dependencies=(dependency,),
    )


def test_batch_foundation_compiles_tracks_skips_and_rebuilds(tmp_path: Path) -> None:
    application = build_application_context(_options(tmp_path / "settings.toml"))
    try:
        resolver = application.services.require(PromptGraphResolver)
        for shot_id in ("SHT-001", "SHT-002"):
            resolver.register(shot_id, _sources(shot_id))

        scheduler = application.services.require(BatchCompilationScheduler)
        first_request = BatchCompilationRequest.create(
            "BATCH-FOUNDATION-001",
            (
                _item("ITEM-002", "SHT-002"),
                _item("ITEM-001", "SHT-001"),
            ),
        )
        scheduler.enqueue(first_request)
        first = scheduler.run_next()

        assert first is not None
        assert first.job is not None
        assert tuple(result.item_id for result in first.job.results) == (
            "ITEM-001",
            "ITEM-002",
        )
        assert all(
            result.status is BatchCompilationItemStatus.COMPLETED
            for result in first.job.results
        )
        assert all(result.package is not None for result in first.job.results)
        assert all(
            "blue-white engine trails" in result.package.positive_prompt
            for result in first.job.results
            if result.package is not None
        )
        assert all(
            "orange engine trails" in result.package.negative_prompt
            for result in first.job.results
            if result.package is not None
        )

        second_request = BatchCompilationRequest.create(
            "BATCH-FOUNDATION-002",
            (
                _item("ITEM-001", "SHT-001"),
                _item("ITEM-002", "SHT-002"),
            ),
        )
        scheduler.enqueue(second_request)
        second = scheduler.run_next()

        assert second is not None
        assert second.job is not None
        assert all(
            result.status is BatchCompilationItemStatus.SKIPPED
            for result in second.job.results
        )

        incremental = application.services.require(IncrementalCompilationHistory)
        affected = incremental.invalidate_dependency(
            CompilationDependencyKind.CANONICAL_ASSET,
            "CAP-SHP-IRON-HORIZON",
        )
        assert affected == ("ITEM-001", "ITEM-002")

        scheduler.enqueue(
            BatchCompilationRequest.create(
                "BATCH-FOUNDATION-003",
                (
                    _item("ITEM-001", "SHT-001"),
                    _item("ITEM-002", "SHT-002"),
                ),
            )
        )
        rebuilt = scheduler.run_next()

        assert rebuilt is not None
        assert rebuilt.job is not None
        assert all(
            result.status is BatchCompilationItemStatus.COMPLETED
            for result in rebuilt.job.results
        )

        history = application.services.require(BatchCompilationHistory)
        tracker = application.services.require(BatchProgressTracker)
        statistics = application.services.require(BatchStatisticsService).calculate()
        reporting = application.services.require(BatchReportingService)
        report = reporting.for_batch("BATCH-FOUNDATION-003")

        assert len(history.all()) == 3
        assert tracker.latest("BATCH-FOUNDATION-003") is not None
        assert statistics.total_batches == 3
        assert statistics.completed_items == 4
        assert statistics.skipped_items == 2
        assert report is not None
        assert "BATCH-FOUNDATION-003" in report.to_markdown()
        recovery = application.services.require(BatchRecoveryService)
        assert recovery.pending_checkpoints() == ()
    finally:
        application.shutdown()


def test_batch_foundation_isolates_invalid_shot_and_reports_failure(
    tmp_path: Path,
) -> None:
    application = build_application_context(_options(tmp_path / "settings.toml"))
    try:
        resolver = application.services.require(PromptGraphResolver)
        resolver.register("SHT-VALID", _sources("SHT-VALID"))
        resolver.register(
            "SHT-INVALID",
            (
                PromptGraphSource(
                    "invalid-intent",
                    PromptNodeKind.VISUAL_INTENT,
                    "Intent",
                    "Incomplete shot intentionally missing camera and lighting.",
                    mandatory=True,
                    sequence=1,
                ),
            ),
        )
        valid = BatchCompilationItem(
            "ITEM-VALID",
            _context("SHT-VALID"),
            require_production_ready=False,
        )
        invalid = BatchCompilationItem(
            "ITEM-INVALID",
            _context("SHT-INVALID"),
            require_production_ready=False,
        )
        scheduler = application.services.require(BatchCompilationScheduler)
        scheduler.enqueue(
            BatchCompilationRequest.create(
                "BATCH-FAILURE-ISOLATION",
                (invalid, valid),
            )
        )

        entry = scheduler.run_next()

        assert entry is not None
        assert entry.job is not None
        outcomes = {result.item_id: result for result in entry.job.results}
        assert outcomes["ITEM-VALID"].status is BatchCompilationItemStatus.COMPLETED
        assert outcomes["ITEM-INVALID"].status is BatchCompilationItemStatus.FAILED
        assert outcomes["ITEM-INVALID"].error_type == "PromptGraphCompilationError"

        report = application.services.require(BatchReportingService).for_batch(
            "BATCH-FAILURE-ISOLATION"
        )
        assert report is not None
        assert report.record.completed_items == 1
        assert report.record.failed_items == 1
    finally:
        application.shutdown()


def test_batch_foundation_restores_only_unfinished_work_after_restart(
    tmp_path: Path,
) -> None:
    settings = tmp_path / "settings.toml"
    request = BatchCompilationRequest.create(
        "BATCH-RESTART-CERTIFICATION",
        (
            _item("ITEM-001", "SHT-001"),
            _item("ITEM-002", "SHT-002"),
        ),
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
        second.services.require(PromptGraphResolver).register(
            "SHT-002",
            _sources("SHT-002"),
        )
        scheduler = second.services.require(BatchCompilationScheduler)
        restored = scheduler.restore_pending()
        finished = scheduler.run_next()

        assert len(restored) == 1
        assert tuple(item.item_id for item in restored[0].request.items) == ("ITEM-002",)
        assert finished is not None
        assert finished.job is not None
        assert tuple(result.item_id for result in finished.job.results) == ("ITEM-002",)
        recovery = second.services.require(BatchRecoveryService)
        assert recovery.pending_checkpoints() == ()
    finally:
        second.shutdown()
