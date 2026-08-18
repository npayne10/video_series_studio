# ADR 0048 — Phase 19.6.12 Production Readiness Integration

## Status

Accepted for implementation; local validation pending.

## Context

Phases 19.6.4–19.6.11 established several independent authorities that together determine whether production work can actually enter runtime execution: ProductionTask dependency readiness, resource/capability matching, deterministic scheduling, immutable schedule revisions, explicit human review, ProductionQueue compilation, worker availability, and runtime monitoring/recovery.

Those authorities intentionally remain separate. Before Phase 19.6.12 there was no single provider-neutral application query that answered whether a production was operationally ready for runtime execution, or explained which authority was preventing readiness.

VSCS also contains an older canonical-image Production Readiness Evaluation (PRE) from Phase 11.7.2. That PRE evaluates technical/semantic/canon image quality and is not the same concern as production scheduling/runtime readiness. Phase 19.6.12 must not replace or reinterpret that asset-level evaluation.

## Decision

1. Introduce `ProductionReadinessIntegrationService` as a read-only application service.
2. The service aggregates existing authoritative state; it does not own another lifecycle and does not mutate any source authority.
3. Readiness is represented by immutable `ProductionReadinessAssessment` and `ProductionReadinessFinding` values.
4. Integrated readiness has three outcomes:
   - `READY` — the approved queue has executable work and matching available resources/workers.
   - `NOT_READY` — required upstream authority is incomplete but not terminally blocked, such as no tasks, no schedule, pending review, or no compiled queue.
   - `BLOCKED` — an existing authority prevents execution, such as blocked/failed/cancelled tasks, schedule deferrals, unavailable/mismatched resources, missing/unavailable workers, or no executable queue entries.
5. Findings use stable codes and severity so future dashboards, APIs, automation, and reporting can consume readiness without parsing presentation text.
6. ProductionTask graph readiness remains owned by `ProductionTaskGraphIntegrationService`; Phase 19.6.12 does not duplicate dependency calculation.
7. Human schedule approval remains authoritative. Readiness cannot approve or alter a schedule.
8. ProductionQueue remains the executable work authority. Readiness cannot compile, claim, start, retry, or complete queue entries.
9. Resources, workers, and queue remain session-scoped in this phase. Therefore a restart may legitimately return `NOT_READY`/`BLOCKED` until session runtime state is reconstructed.
10. `ProductionSchedulingUiService.production_readiness()` exposes the integrated assessment through the existing application facade without adding provider/model/workflow concepts.
11. Presentation changes are deliberately excluded from Phase 19.6.12. The assessment API is suitable for a later production dashboard/readiness UI without reopening the accepted Phase 19.6.11 scheduling widget contract.

## Consequences

- VSCS gains one deterministic production-level readiness query across the full scheduling/runtime preparation chain.
- Operators and future automation can distinguish incomplete preparation from genuine execution blockers.
- Existing authority boundaries remain intact and auditable.
- The assessment immediately exposes the current session-persistence limitation instead of hiding it.
- Provider neutrality is preserved; no ComfyUI, model, renderer, GPU brand, or cloud-provider detail enters production authority.

## Deliberately deferred

- Durable ProductionResource persistence/discovery.
- Durable ProductionWorker persistence/discovery.
- ProductionQueue and execution-lease persistence across restart.
- Provider/executor readiness and health checks.
- GPU/VRAM/capacity telemetry.
- Production readiness dashboard/UI.
- Automatic claim/start/execution based on readiness.
- ProductionTask lifecycle reconciliation from runtime completion.
- Asset-level PRE/CIEE/SIEE redesign or migration.
