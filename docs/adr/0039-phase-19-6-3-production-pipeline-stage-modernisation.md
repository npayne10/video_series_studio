# ADR-0039 — Phase 19.6.3 Production Pipeline Stage Modernisation

**Status:** Accepted  
**Phase:** 19.6.3  
**Decision:** ProductionTask becomes the authoritative provider-neutral production lifecycle record at the legacy render execution boundary, while the existing RenderJob, RenderQueue and ProductionPipeline structures remain compatibility projections during incremental migration.

## Context

Phase 19.6.1 established the governed `ProductionTask` domain and Phase 19.6.2 established deterministic compilation from current approved Universal Production Description authority. The existing production execution path, however, still operates through `RenderJob`, `RenderQueueEntry`, `ProductionPipeline` and `ProductionNode`.

Repository tracing identifies `RenderExecutionService` in `vscs.infrastructure.production.execution` as the current legacy execution boundary. It claims and starts a `RenderQueueEntry`, selects an executor for a legacy `RenderJob`, executes it, and reconciles the matching legacy `ProductionNode` at the `RENDERING` stage.

Replacing this path in one step would combine lifecycle migration, scheduling migration, provider/workflow selection and executor migration. That would violate the incremental compatibility-first VSCS migration strategy.

## Decision

### 1. ProductionTask lifecycle authority

A provider-neutral `ProductionTaskStageService` owns valid task-state transitions. The authoritative lifecycle is:

- `PLANNED -> READY | BLOCKED | CANCELLED | SUPERSEDED`
- `READY -> BLOCKED | RUNNING | CANCELLED | SUPERSEDED`
- `BLOCKED -> READY | CANCELLED | SUPERSEDED`
- `RUNNING -> COMPLETED | FAILED | CANCELLED`
- `FAILED -> READY | CANCELLED | SUPERSEDED`
- `COMPLETED`, `CANCELLED` and `SUPERSEDED` are terminal.

`ProductionTaskLifecycleService` applies these transitions through a repository boundary and persists the resulting authoritative task state.

### 2. Persistence boundary

The application layer depends on the `ProductionTaskRepository` protocol rather than a storage technology. Phase 19.6.3 provides `JsonProductionTaskRepository` as a durable atomic filesystem adapter. Storage is therefore replaceable without changing ProductionTask lifecycle semantics.

`ProductionTaskApplicationService` connects governed task compilation to persistence without changing the deterministic Phase 19.6.2 compiler contract.

### 3. Compatibility instead of destructive replacement

The existing production pipeline remains operational. `ProductionTaskLegacyBridge` provides a one-way projection from authoritative ProductionTask state into the legacy rendering node and can attach `production_task_id` to existing queue-entry metadata without changing the queue schema.

Legacy `ProductionNode` and `RenderQueueEntry` state must not become a second authority for ProductionTask state.

### 4. Legacy execution wrapper

`ProductionTaskRenderExecutionService` wraps, rather than replaces, `RenderExecutionService`. It persists ProductionTask lifecycle transitions around the existing render execution and returns the unchanged legacy execution outcome as a compatibility result with its pipeline state projected from the final task state.

A legacy retry is represented authoritatively as `RUNNING -> FAILED -> READY`; the legacy queue remains responsible for its existing retry timing and attempt bookkeeping during this phase.

### 5. Provider neutrality remains intact

Phase 19.6.3 does not move provider selection, workflow selection, worker selection, queue scheduling or renderer-specific execution into `ProductionTask`. Those remain downstream compatibility concerns until their dedicated migration phases.

### 6. No UI change in this phase

No presentation-layer changes are required to establish the backend migration seam. UI exposure is deferred until the lifecycle, compatibility, persistence and regression contracts are stable.

## Consequences

- New code can treat `ProductionTask` as the production lifecycle authority without breaking existing render execution.
- Existing RenderJob/queue/executor integrations remain usable while migration proceeds incrementally.
- ProductionTask state survives application restart through an explicit repository boundary.
- The compatibility bridge is deliberately one-way, preventing silent legacy-state promotion into governed authority.
- Phase 19.6.4 can migrate additional queue/execution responsibilities onto ProductionTask without requiring another big-bang rewrite.

## Rejected alternatives

### Replace ProductionPipeline and RenderQueue immediately

Rejected because it would couple several migration concerns and create unnecessary regression risk.

### Add provider or workflow fields to ProductionTask

Rejected because ProductionTask is a provider-neutral governed work contract, not an execution-provider configuration object.

### Keep ProductionNode as lifecycle authority and merely reference ProductionTask

Rejected because it would preserve the duplicate authority that Phase 19.6 is intended to remove.
