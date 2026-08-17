# ADR 0040 — Phase 19.6.4 ProductionGraph Integration

## Status

Accepted for implementation in Phase 19.6.4.

## Context

Phase 19.6.2 established governed, provider-neutral `ProductionTask` compilation from approved Universal Production Description authority. Phase 19.6.3 made `ProductionTask` the authoritative lifecycle record while preserving the established `RenderJob`, `RenderQueueEntry`, `ProductionPipeline`, and `ProductionNode` execution path as a compatibility projection.

The existing `ProductionGraph` still analyzes legacy `ProductionNode` objects. `ProductionTask` already owns a task-to-task `dependencies` contract, so dependency readiness must move to the new authority without destructively rewriting the legacy pipeline or moving provider/workflow execution concerns upstream.

## Decision

### 1. Add a ProductionTask-native graph

Introduce `ProductionTaskGraph` in the ProductionTask application package. The graph:

- accepts only `ProductionTask` records;
- rejects duplicate task identities;
- rejects graphs mixing production identities;
- rejects unknown dependency identities;
- detects dependency cycles;
- produces deterministic topological ordering;
- classifies dependency disposition as `READY`, `WAITING`, or `BLOCKED`.

The established legacy `ProductionGraph` remains unchanged for compatibility.

### 2. Define dependency readiness conservatively

A ProductionTask is dependency-ready only when every declared dependency is `COMPLETED`.

A task with healthy but incomplete dependencies remains waiting. Waiting does not mean failure and does not automatically change a `PLANNED` task to `BLOCKED`.

A dependency in `BLOCKED`, `FAILED`, `CANCELLED`, or `SUPERSEDED` makes its downstream chain blocked. Blocking propagates through descendants so a task cannot become executable merely because the direct dependency has not yet been persisted as blocked.

### 3. Persist graph-derived lifecycle state without executing

Introduce `ProductionTaskGraphIntegrationService` at the application boundary. It loads tasks for one production through `ProductionTaskRepository`, builds the graph, and persists only these graph-derived transitions:

- `PLANNED -> READY` when all dependencies are complete;
- `BLOCKED -> READY` when the dependency chain has recovered and all dependencies are complete;
- `PLANNED -> BLOCKED` or `READY -> BLOCKED` when an unavailable dependency chain is detected.

`RUNNING` and terminal tasks are never changed by graph refresh.

Graph refresh does not select a provider, workflow, worker, render job, queue entry, schedule, or executor and does not begin execution.

### 4. Preserve Phase 19.6.3 compatibility

The legacy render pipeline remains available. `ProductionTaskLegacyBridge` continues to project authoritative task state into legacy rendering nodes where required. No reverse authority is introduced from `ProductionNode` or `RenderQueueEntry` into `ProductionTask`.

### 5. Production scope is explicit

Graph integration uses `ProductionTaskRepository.list_for_production()` and refuses mixed-production graphs. This prevents dependencies from being resolved accidentally across production boundaries.

## Consequences

- Production dependency order and readiness now have a provider-neutral authoritative representation.
- Root ProductionTasks can become `READY` without any legacy node being authoritative.
- Downstream tasks remain safely `PLANNED` until dependencies complete.
- Failed, cancelled, superseded, or blocked dependency chains prevent downstream execution eligibility.
- Legacy orchestration remains operational during incremental migration.
- Provider selection, workflow compilation, queue scheduling, retries, worker leases, and actual execution remain downstream concerns for later phases.

## Validation

Phase 19.6.4 focused regression coverage must verify:

- deterministic topological ordering;
- unknown-dependency rejection;
- cycle rejection;
- duplicate and mixed-production rejection;
- READY/WAITING/BLOCKED dependency classification;
- transitive blocking;
- persisted readiness transitions without execution;
- production-scoped graph refresh;
- preservation of the existing Phase 19.6.3 and full VSCS regression suites.
