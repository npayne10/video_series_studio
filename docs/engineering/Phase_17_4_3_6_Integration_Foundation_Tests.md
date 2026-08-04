# Phase 17.4.3.6 — Integration and Foundation Tests

## Objective

Certify the complete Batch Prompt Compilation foundation as one integrated production subsystem.

The phase validates the full application path:

```text
BatchCompilationRequest
→ BatchCompilationScheduler
→ BatchPromptCompilationService
→ PromptGraphBuilder
→ PromptGraphValidator
→ PromptGraphCompiler
→ RendererPromptCompiler
→ IncrementalCompilationHistory
→ Progress / History / Reporting
→ Recovery Checkpoint
```

## Certified capabilities

### Deterministic batch orchestration

- Input order does not alter compilation order.
- Shot sequence remains stable.
- Successful packages retain renderer-profile provenance.
- Positive and negative prompt content remain separated.

### Queue execution

- Requests execute through the bootstrapped FIFO scheduler.
- Jobs move through the approved scheduler lifecycle.
- Batch results remain available after completion.

### Incremental compilation

- A first request compiles changed work.
- An identical request reuses the previous package and reports `skipped`.
- Canonical dependency invalidation identifies affected items.
- Invalidated items compile again without rebuilding unrelated work.

### Failure isolation

- An invalid shot fails validation and compilation safely.
- A valid shot in the same batch still completes.
- The terminal batch report contains the correct success and failure counts.
- No rendering operation is involved in this phase.

### Progress, history and reporting

- Live progress reaches the shared `BatchProgressTracker`.
- Terminal jobs are recorded in `BatchCompilationHistory`.
- Aggregate compiled and skipped counts are available through
  `BatchStatisticsService`.
- Deterministic Markdown reporting remains available through
  `BatchReportingService`.

### Resume and recovery

- Per-item results are checkpointed to the isolated recovery store.
- A restarted application restores only unfinished items.
- Completed work is not repeated.
- A fully completed checkpoint is no longer returned as pending recovery work.

## Certification suite

The final integrated suite is:

```text
tests/integration/test_batch_compilation_foundation_integration.py
```

It contains three representative production scenarios:

1. Multi-shot compilation, incremental skipping, dependency invalidation,
   rebuilding, observability and completed recovery state.
2. Validation failure isolation within a mixed valid/invalid batch.
3. Application restart with restoration of only unfinished work.

The suite supplements rather than replaces the focused unit and integration tests
created in Phases 17.4.3.1 through 17.4.3.5.

## Safety guarantees

- Batch processing remains renderer-neutral until renderer-profile formatting.
- Failed items do not terminate unrelated work.
- Completed and skipped work is reusable.
- Incomplete recovery checkpoints cannot silently accept changed requests.
- Test-mode recovery data is isolated from production configuration.
- Prompt compilation remains deterministic for identical source data and profiles.

## Deliberate exclusions

Phase 17.4.3 does not execute ComfyUI and does not provide:

- GPU or render scheduling
- Distributed workers
- Live rendering retries
- Production dashboard UI
- Persistent incremental package storage beyond recovery checkpoints
- Remote queue control

Those capabilities belong to later rendering and Production Workspace phases.

## Readiness decision

When the complete Phase 17.4.3 test matrix passes, the Batch Prompt Compilation
foundation is approved for use by later UI, render-queue and automation phases.

The subsystem can compile multiple shots, preserve deterministic order, skip
unchanged work, rebuild invalidated dependencies, isolate failures, expose progress
and reporting, and resume unfinished batches after restart.
