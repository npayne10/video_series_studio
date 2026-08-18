# ADR 0047 — Phase 19.6.11 Production Scheduling UI

## Status

Accepted for implementation; local validation pending.

## Context

Phases 19.6.4–19.6.10 established provider-neutral dependency readiness, resource matching, deterministic scheduling, immutable schedule revisions, explicit human review, ProductionQueue generalisation, worker/claim/lease/retry integration, and scheduling monitoring/recovery.

The existing Production Planning workspace already contains the governed ProductionTask compiler introduced in Phase 19.6.2. Its compiled tasks were retained in workspace memory, while the scheduling application services correctly consume the durable ProductionTask repository. A scheduling UI therefore needs both an operator-facing workflow and a narrow persistence bridge from compiled ProductionTasks into the existing repository boundary.

## Decision

1. Production Scheduling is added as a tab inside the existing Production Planning workspace. No second scheduling window or duplicate navigation hierarchy is introduced.
2. Widget code remains a presentation layer. Scheduling, readiness, review, queue compilation, monitoring, and recovery decisions are delegated to application services.
3. `ProductionSchedulingUiService` is the application facade for UI commands/queries. It depends on repository protocols through injected repository factories; concrete JSON repositories are composed in the presentation integration layer using the active project directory.
4. ProductionTask compiler output is registered in the durable ProductionTask repository before scheduling. Registration is idempotent for the same governed task contract and rejects conflicting governed content rather than silently overwriting it.
5. Schedule review remains explicit human authority. Reviewer identity and notes are entered in the UI; the UI never auto-approves a schedule.
6. Queue compilation is enabled only for the current APPROVED schedule revision. Compiling the queue does not start external execution.
7. Resource and worker registration are explicitly labelled session-scoped because resource discovery/persistence and worker persistence remain deferred. ProductionQueue runtime state also remains session-scoped.
8. Monitoring is observational. Recovery is an explicit operator action that delegates to the Phase 19.6.10 recovery service and Phase 19.6.9 runtime state owner.
9. Provider/model/workflow/ComfyUI details are not exposed in this scheduling authority UI.
10. Phase 19.6.11 adds real Qt UI tests in addition to application-service tests.

## Consequences

- Operators can now see and operate the governed scheduling chain from Production Planning without manipulating backend objects manually.
- The existing ProductionTask compiler feeds the durable scheduling authority rather than a parallel UI-only model.
- Application-layer scheduling UI logic remains testable without Qt or concrete repository dependencies.
- The UI makes the human review gate visible before queue compilation.
- Runtime resource/worker/queue information is deliberately lost on application restart until later persistence phases introduce durable runtime state.
- Existing legacy RenderQueue/renderer UI and execution paths remain unchanged.

## Deliberately deferred

- ProductionResource persistence/discovery and health polling.
- ProductionWorker persistence/discovery.
- ProductionQueue/lease persistence across restart.
- GPU/VRAM telemetry and capacity scheduling.
- Worker claim/start/heartbeat controls in this operator tab.
- ProductionTask lifecycle reconciliation from queue execution.
- RenderJob/provider/executor selection and submission.
- ComfyUI workflow/model controls.
- Production QA and repair routing.
