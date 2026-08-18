# ADR 0046 — Phase 19.6.10 Scheduling Monitoring & Recovery

## Status
Accepted for implementation; local validation pending.

## Context
Phase 19.6.8 established the provider-neutral `ProductionQueue`. Phase 19.6.9 added provider-neutral workers, claims, execution leases, heartbeats and retry recovery. VSCS already contains mature monitoring and recovery components in the legacy Production Pipeline, but those components are coupled to `RenderQueue`, `RenderJob.job_id`, legacy `ProductionPipeline`, `WorkerIdentity` and render-specific `ExecutionLease`.

Phase 19.6.10 must make the new scheduling runtime observable and recoverable without merging the new ProductionTask execution authority back into render-specific contracts or duplicating retry state-transition ownership.

## Decision
Introduce a provider-neutral scheduling monitoring layer in `vscs.application.production_tasks`.

`ProductionSchedulingMonitor` builds immutable snapshots over `ProductionQueue`, `ProductionWorker` and `ProductionExecutionLease`. It reports queue progress, worker/runtime ownership and actionable diagnostics. Monitoring is observational and never mutates queue, task, schedule or worker state.

Diagnostics include active work without a lease, expired leases, stalled queue entries, unregistered/unavailable claimed workers, blocked entries and failed entries. Diagnostics reference ProductionTask and scheduled resource identities rather than RenderJob or provider details.

Introduce `ProductionSchedulingRecoveryService` as a thin coordination/reporting layer over `ProductionQueueRuntimeService.recover_expired_leases()`. The runtime service remains the owner of queue mutation and retry semantics. The recovery service records deterministic decisions and immutable events for expired claims and running leases.

Recovery rules remain:

- expired CLAIMED work returns to READY without consuming an attempt;
- expired RUNNING work records a failed attempt and follows the ProductionTask-derived retry policy;
- attempts remaining produce RETRYING/READY according to retry delay;
- exhausted attempts produce FAILED.

The legacy `ProductionMonitor` and `ProductionRecoveryEngine` remain unchanged for RenderQueue compatibility.

## Consequences
The modern scheduling path now has provider-neutral monitoring and explicit recovery evidence without requiring RenderJob identities. Future dashboard/query services can consume the immutable monitoring snapshot. Future persistence can store recovery events without changing the recovery rules.

The new monitoring layer does not perform provider health checks, GPU telemetry, output inspection or ProductionTask lifecycle reconciliation. Those remain later explicit integration boundaries.

## Compatibility
No existing RenderQueue, ProductionPipeline, monitoring, recovery, executor, ComfyUI or provider contracts are removed or changed. The migration remains incremental.
