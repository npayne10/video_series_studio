# Phase 17.4.3.4 — Progress, History and Reporting

## Objective

Provide operational visibility for batch prompt compilation without changing Prompt Graph, validation, compilation, renderer-profile or incremental-build behavior.

## Architecture

```text
BatchCompilationScheduler
    -> BatchPromptCompilationService progress callbacks
    -> BatchProgressTracker
    -> terminal BatchCompilationJob
    -> BatchCompilationHistory
    -> BatchStatisticsService
    -> BatchReportingService
```

## Progress tracking

`BatchProgressTracker` retains immutable timestamped snapshots. Calculated metrics include elapsed time, estimated remaining time, processed items per minute and success rate. The tracker is updated by the scheduler for every compiler progress callback and terminal job state.

## History

`BatchCompilationHistory` stores immutable `BatchHistoryRecord` instances in completion order. Records contain item outcome totals, duration, renderer and quality identities, renderer profiles, workflow IDs, graph versions and a deterministic result checksum.

Supported queries include latest record, batch lookup, completed batches, failed batches and the last requested number of records.

## Statistics

`BatchStatisticsService` calculates aggregate production metrics including total batches and items, completed/skipped/failed/cancelled counts, average duration, fastest and slowest batch, average throughput, completion percentage, failure rate and skip rate.

## Reporting

`BatchReportingService` produces immutable `BatchCompilationReport` models. Reports support deterministic plain-text and Markdown formatting with summary, production results, timing, provenance and failure diagnostics.

## Bootstrap integration

The application composition root registers shared instances of:

- `BatchProgressTracker`
- `BatchCompilationHistory`
- `BatchStatisticsService`
- `BatchReportingService`

The `BatchCompilationScheduler` receives the shared progress tracker and reporting service.

## Deliberate exclusions

This phase does not add database or file persistence, restart recovery, a Production dashboard, live rendering or remote monitoring. Persistence and recovery remain in Phase 17.4.3.5.

## Readiness

The subsystem is ready to supply live and historical operational data to the future Production Workspace without requiring changes to the batch compiler or scheduler contracts.
