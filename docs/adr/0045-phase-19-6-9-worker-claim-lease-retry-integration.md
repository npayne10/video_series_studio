# ADR 0045 — Phase 19.6.9 Worker, Claim, Lease & Retry Integration

## Status

Accepted architecture; implementation pending local validation.

## Context

Phase 19.6.8 introduced `ProductionQueue` as the provider-neutral runtime queue for approved `ProductionTask` work. The older execution layer already contains useful worker and lease concepts, but its `WorkerIdentity`, `ExecutionLease`, and executor contracts are tied to `RenderCapability`, `RenderJob`, and `job_id`.

Using those render-specific types directly for the general queue would leak renderer semantics back into provider-neutral production orchestration.

Phase 19.6.9 therefore needs to integrate worker ownership, claims, leases, heartbeats, lease expiry, and retries around `ProductionQueue` while preserving the existing renderer execution path for compatibility.

## Decision

Introduce provider-neutral runtime worker and lease contracts in the ProductionTask application layer:

- `ProductionWorker`
- `ProductionWorkerState`
- `ProductionWorkerRegistry`
- `ProductionExecutionLease`
- `ProductionLeaseManager`
- `ProductionQueueClaim`
- `ProductionQueueRuntimeService`

A `ProductionWorker` binds a runtime worker identity to one scheduled `ProductionResource` identity and advertises provider-neutral `ProductionCapability` values.

A worker may claim a queue entry only when:

1. the queue entry is `READY`;
2. the worker is registered and `AVAILABLE`;
3. the worker's `resource_id` matches the resource selected by the approved ProductionSchedule;
4. the current ProductionTask exists; and
5. the worker advertises every capability currently required by that ProductionTask.

A successful claim acquires a time-bound `ProductionExecutionLease` and changes the queue entry to `CLAIMED`.

Starting, heartbeating, completing, or failing work requires an active lease whose queue, entry, task, and worker ownership match the current queue state.

One worker may hold at most one active lease. One queue entry may have at most one active lease.

Completing or failing an attempt releases the lease. Failure continues to use the retry policy already copied from `ProductionTaskAttemptPolicy` into `ProductionQueueEntry` by Phase 19.6.8.

Expired leases are recovered deterministically:

- an expired `CLAIMED` entry returns to `READY` without consuming an attempt;
- an expired `RUNNING` entry records a failed attempt with `execution lease expired` and follows its configured retry policy;
- when attempts are exhausted, the entry becomes `FAILED`.

## Compatibility

The existing render-specific contracts remain unchanged:

- `WorkerIdentity`
- `ExecutionLease`
- `LeaseManager`
- `RenderQueue`
- `RenderJob`
- `ExecutorRegistry`
- `RenderExecutionService`

They remain the compatibility execution path until a later explicit execution migration phase.

## Provider Neutrality

The new worker/lease layer contains no:

- ComfyUI concepts;
- provider IDs;
- workflow IDs;
- model IDs;
- render-job capabilities;
- endpoint configuration.

Concrete executor/provider selection remains downstream.

## Persistence

ProductionTask persistence remains authoritative for production work. ProductionQueue and execution-lease persistence are intentionally deferred. Phase 19.6.9 establishes runtime semantics first; durable queue/lease recovery can be added without changing the provider-neutral contracts.

## Consequences

Positive:

- approved schedule resource assignment is enforced at claim time;
- workers cannot silently take incompatible work;
- abandoned claims recover safely;
- abandoned running work consumes an attempt and enters the normal retry path;
- heartbeat and ownership validation prevent stale workers from completing another worker's task;
- non-render task types use the same runtime coordination model.

Deferred:

- durable ProductionQueue persistence;
- durable lease persistence and process-restart recovery;
- worker discovery/health polling;
- resource capacity greater than one concurrent lease;
- task lifecycle reconciliation with queue runtime state;
- provider/executor translation and execution submission;
- UI monitoring and manual lease recovery controls.
