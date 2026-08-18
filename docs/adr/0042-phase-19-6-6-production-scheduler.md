# ADR 0042 — Phase 19.6.6 Production Scheduler

## Status

Accepted for implementation in Phase 19.6.6.

## Context

Phase 19.6.4 established authoritative ProductionTask dependency readiness and Phase 19.6.5 introduced provider-neutral ProductionResource capability matching. The next boundary is to decide which READY ProductionTasks should receive currently compatible resources and in what deterministic order, without collapsing scheduling into provider execution.

The legacy RenderQueueEngine already owns runtime queue mechanics such as claims, retries, attempt tracking and queue-state transitions. Those mechanics must not be duplicated in the ProductionTask authority layer.

## Decision

### 1. Schedule only authoritative READY ProductionTasks

The ProductionScheduler consumes ProductionTask records whose authoritative lifecycle state is READY. PLANNED, BLOCKED, RUNNING and terminal tasks are ignored by the scheduling pass. The scheduler does not change ProductionTask lifecycle state.

Dependency evaluation remains owned by the Phase 19.6.4 ProductionTask graph. Scheduling therefore relies on persisted READY state rather than reimplementing dependency rules.

### 2. Order tasks deterministically

READY tasks are considered in this order:

1. ProductionTaskPriority descending;
2. created_at ascending;
3. task_id ascending.

This preserves explicit production priority while providing stable tie-breaking.

### 3. Match resources through the Phase 19.6.5 catalog

For each READY task, the scheduler uses ProductionResourceCatalog capability evaluation. A resource must be AVAILABLE and satisfy every required ProductionCapability.

The scheduler distinguishes three deferral conditions:

- NO_CAPABLE_RESOURCE — no resource advertises all required capabilities;
- NO_AVAILABLE_RESOURCE — capable resources exist but none are currently available;
- RESOURCE_ALREADY_ASSIGNED — compatible available resources exist but have already received another task during the same scheduling pass.

### 4. One resource identity receives at most one task per scheduling pass

A ProductionResource identity represents one schedulable resource slot for the current planning snapshot. This allows distinct resources to be scheduled in parallel without double-assigning one resource identity in the same pass.

This is not a runtime lease or capacity reservation. Future execution planning may introduce explicit concurrency/capacity models where required.

### 5. Scheduling produces a provider-neutral snapshot only

ProductionSchedule records task-to-resource assignments and deferrals. It does not:

- select a renderer, provider, model, workflow or endpoint;
- create RenderJobs;
- create or claim RenderQueueEntry records;
- acquire worker leases;
- start execution;
- record execution attempts;
- alter governed production authority.

Concrete executor selection and runtime queue mechanics remain downstream.

### 6. Preserve legacy execution compatibility

RenderQueueEngine, ExecutorRegistry, WorkerIdentity, ExecutionLease and RenderCapability remain unchanged. Later migration phases may project scheduled ProductionTasks into that execution path, but legacy runtime state does not become ProductionTask authority.

## Consequences

- VSCS now has an authoritative provider-neutral scheduling boundary above concrete execution.
- Priority affects scheduling deterministically.
- Multiple distinct production resources can receive work in one pass.
- Missing, unavailable and already-assigned resources produce explicit actionable deferrals.
- Scheduling is repeatable and side-effect free.
- Existing runtime queue, retry, lease and executor infrastructure remains available for incremental migration.

## Validation

Phase 19.6.6 focused coverage must verify:

- production-scope validation;
- READY-only scheduling;
- no lifecycle mutation;
- deterministic priority/age/identity ordering;
- deterministic compatible-resource selection;
- no-capability deferral;
- unavailable-resource deferral;
- prevention of duplicate resource assignment in one pass;
- production-scoped repository integration;
- preservation of persisted ProductionTask state;
- preservation of existing Phase 19.6 and full VSCS regression suites.
