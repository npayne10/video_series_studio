# ADR 0041 — Phase 19.6.5 Production Resource & Capability Model

## Status

Accepted for implementation in Phase 19.6.5.

## Context

Phase 19.6.2 established governed provider-neutral `ProductionTask` compilation. Phase 19.6.3 established authoritative ProductionTask lifecycle persistence while retaining the legacy execution path as a compatibility projection. Phase 19.6.4 moved dependency ordering and readiness into a ProductionTask-native graph without starting execution.

`ProductionTask.capabilities` now states what broad production capability governed work requires. The legacy execution system already has `WorkerIdentity`, `ProductionExecutor`, `ExecutorRegistry`, and renderer-oriented `RenderCapability` values. Those renderer capabilities describe how a concrete render job can be executed and are intentionally more specific than the production capabilities carried by ProductionTask.

The architecture requires a provider-neutral boundary between governed production work and later execution planning:

`ProductionTask -> capability/resource matching -> execution planning -> provider adapter`

The resource model must therefore identify resources capable of satisfying ProductionTask requirements without selecting a provider, renderer, workflow, model, endpoint, worker lease, or concrete execution job.

## Decision

### 1. Introduce a provider-neutral ProductionResource

Add immutable `ProductionResource` records containing:

- stable `resource_id`;
- a set of `ProductionCapability` values;
- provider-neutral availability state;
- optional labels;
- optional metadata.

Phase 19.6.5 availability is intentionally minimal: `AVAILABLE` or `UNAVAILABLE`. Capacity, concurrency, health scoring, cost, locality, leases, reservations, and scheduling policy are not represented yet.

### 2. Reuse ProductionCapability as the matching vocabulary

Do not introduce a second coarse production-capability taxonomy. `ProductionResource.capabilities` uses the same `ProductionCapability` enum already required by `ProductionTask`.

A resource is capability-compatible when every capability required by the task is present in the resource capability set.

### 3. Keep renderer capabilities separate

Do not translate `ProductionCapability` directly into legacy ACPP `RenderCapability` inside the production authority layer.

For example, `VIDEO_GENERATION` describes the production work category, while `TEXT_TO_VIDEO`, `IMAGE_TO_VIDEO`, `START_FRAME_CONDITIONING`, and similar values describe concrete renderer requirements. The mapping between those layers belongs to later execution planning and adapter compilation.

The existing `WorkerIdentity`, `ProductionExecutor`, `ExecutorRegistry`, `RenderJob`, and `RenderCapability` contracts remain unchanged.

### 4. Match resources deterministically without selecting one

Introduce `ProductionResourceCatalog` as an immutable catalog snapshot. It:

- rejects duplicate resource identities;
- returns resources in deterministic identity order;
- evaluates every resource against one ProductionTask;
- reports missing capabilities explicitly;
- excludes unavailable resources from candidates;
- returns every eligible candidate rather than choosing one.

Resource selection, ranking, reservation, leasing, scheduling, and execution are downstream responsibilities.

### 5. Resource matching does not own ProductionTask lifecycle

Capability matching is observational. It does not transition `PLANNED`, `READY`, or any other ProductionTask lifecycle state.

Phase 19.6.4 dependency readiness remains authoritative for graph-derived readiness. A later execution-planning layer may require both a `READY` ProductionTask and a suitable resource before dispatch, but Phase 19.6.5 does not dispatch work.

### 6. No UI or persistent resource registry in this phase

This phase establishes the typed resource/capability contract and deterministic matching semantics only. Resource discovery, persistence, dynamic health, assignment, provider adapter mapping, scheduling, and UI presentation are deferred until a later phase explicitly owns them.

## Consequences

- ProductionTasks can now be matched to abstract production resources without provider leakage.
- Exact and capability-superset resources are supported naturally.
- Missing capability diagnostics are deterministic and inspectable.
- Unavailable resources cannot become execution candidates.
- The legacy executor registry remains available while execution migration continues incrementally.
- Production capability requirements remain distinct from renderer-specific technical capabilities.
- No task state, graph state, queue state, lease, provider, or workflow is mutated by matching.

## Validation

Phase 19.6.5 focused regression coverage must verify:

- resource identity and capability invariants;
- duplicate catalog identity rejection;
- deterministic resource ordering;
- exact capability matching;
- capability-superset matching;
- explicit missing-capability diagnostics;
- unavailable-resource exclusion;
- absence of ProductionTask lifecycle mutation;
- label and metadata invariants;
- preservation of the Phase 19.6.4 and full VSCS regression suites.
