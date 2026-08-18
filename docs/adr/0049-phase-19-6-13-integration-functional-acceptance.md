# ADR 0049 — Phase 19.6.13 Integration & Functional Acceptance

## Status

Accepted for implementation; local and functional validation pending.

## Context

Phases 19.6.1–19.6.12 established the governed provider-neutral production scheduling chain:

- ProductionTask domain and governance.
- Deterministic compilation from approved production authority.
- Modernised production pipeline stages.
- ProductionTask dependency/readiness graph integration.
- ProductionResource capability model.
- Deterministic scheduling.
- Durable schedule revisions and explicit human review.
- General ProductionQueue compilation.
- Worker, claim, lease, heartbeat and retry runtime coordination.
- Scheduling monitoring and recovery.
- Production Scheduling UI.
- Integrated production-level readiness assessment.

The individual subphases have focused unit/integration coverage, but Phase 19.6 requires a final cross-boundary functional acceptance step before the scheduling architecture can be treated as an integrated production capability.

## Decision

1. Phase 19.6.13 introduces no new production authority or lifecycle state.
2. Acceptance exercises the existing public application/runtime contracts across real JSON ProductionTask and ProductionSchedule persistence boundaries.
3. The acceptance happy path is:
   `ProductionTask → graph READY → resource schedule → explicit human approval → ProductionQueue → worker → ProductionReadiness READY → claim → lease → RUNNING → heartbeat → monitoring → COMPLETED`.
4. The human approval gate is explicitly tested by proving queue compilation fails before approval.
5. Integrated readiness is explicitly tested before and after worker registration.
6. Runtime recovery is explicitly tested by expiring a RUNNING lease and verifying retry routing plus recovery decision/event emission.
7. Phase 19.6.13 does not submit work to ComfyUI, a renderer, model, cloud service, or any provider adapter. Runtime execution-provider integration remains outside Phase 19.6.
8. The existing Phase 19.6.11 Scheduling UI receives a manual functional acceptance pass; no new UI is introduced by this phase.
9. Acceptance does not weaken or replace the focused tests from Phases 19.6.1–19.6.12; the full test suite remains mandatory.

## Consequences

- Phase 19.6 gains one deterministic end-to-end acceptance suite rather than relying only on isolated subphase tests.
- Governance, persistence, scheduling, review, queue, runtime, monitoring, recovery and readiness boundaries are validated together.
- Provider neutrality is preserved.
- Existing deliberate limitations remain visible: resource/worker/queue/lease runtime state is session-scoped, and runtime completion is not yet reconciled back into durable ProductionTask lifecycle authority.

## Deliberately deferred

- Provider/executor submission and result handling.
- ComfyUI/LTX/model/workflow selection.
- Durable ProductionResource and ProductionWorker persistence/discovery.
- Durable ProductionQueue and execution lease persistence across restart.
- Runtime-to-ProductionTask completion/failure reconciliation.
- GPU/VRAM capacity telemetry.
- Distributed worker coordination.
- Production QA/output validation and repair routing.
