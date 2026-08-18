# ADR 0056 — Phase 20.7 Durable Execution Jobs & Attempts

## Status

Accepted for implementation; local validation pending.

## Context

Phase 20.6 proved live queue-authorised ComfyUI execution end-to-end, but provider execution state remained transient. `ProviderExecutionHandle.native_handle`, ComfyUI prompt identity, provider state, progress, and execution observations were lost if VSCS stopped.

Phase 19 already owns queue attempts, worker claims, leases, retry policy, and completion authority. Phase 20.7 must make provider execution restart-visible without creating a second execution authority.

## Decision

Introduce one durable `DurableExecutionJob` for each Phase 19 queue attempt.

The existing deterministic `ProviderExecutionContext.execution_id` remains the stable identity. Because it includes the queue entry and attempt number, Phase 20.7 does not create a separate retry counter or provider-attempt authority.

A durable execution job persists:

- VSCS execution identity;
- production, task, queue, and queue-entry identity;
- scheduled resource, worker, and lease identity;
- Phase 19 attempt number;
- production-authority fingerprint;
- provider identity and provider job identity;
- render request and workflow identity;
- submitted/created/updated timestamps;
- provider-neutral execution state and progress;
- failure reason;
- provider-handle metadata required for later reconstruction;
- immutable chronological execution observations.

Native provider objects such as `RenderJob` are never serialized.

## Persistence

Use a schema-versioned project-local JSON repository consistent with existing VSCS persistence patterns:

- one document per stable execution identity;
- filesystem-safe identities;
- atomic temporary-file replacement;
- deterministic queries for task, queue entry, provider, and active jobs;
- complete reconstruction into immutable application records.

## Queue integration

`QueueProviderExecutionService` accepts an optional `DurableExecutionJobService` dependency for backward compatibility.

When configured:

1. after Phase 19 starts the queue attempt and produces `ProviderExecutionContext`, a PREPARING durable record is persisted before live provider submission;
2. a successful provider submission persists provider job identity and handle metadata;
3. every meaningful provider observation updates the durable record and appends an immutable observation event;
4. submission failure before provider acceptance is persisted as FAILED;
5. completion, provider failure, and cancellation are persisted before the corresponding Phase 19 terminal queue transition.

Phase 19 remains authoritative for queue lifecycle and retry behavior.

## Provider submission vs persistence failure

Once a provider has accepted a job, a later durable-persistence error must not cause VSCS to mark the queue attempt failed or release the lease while the external provider may still be rendering. The queue therefore remains RUNNING with its live handle and active lease. This prevents orphaned external execution.

Before provider acceptance, compilation, validation, persistence, or submission failures continue through normal Phase 19 failure/retry handling.

## Terminal history

Provider observations may skip intermediate states because provider APIs do not guarantee identical lifecycle granularity. However, once a durable job is COMPLETED, FAILED, or CANCELLED, a later stale observation cannot move it back to a non-terminal state.

Provider job identity cannot change during one durable execution.

## Restart boundary

Phase 20.7 persists the information required for later restart reconciliation, including active-job discovery and provider-handle metadata. It does **not** itself re-register workers/resources, reconstruct live provider handles, query providers after restart, or reconcile queue state. Those behaviors remain in the approved restart/recovery phases.

## Generated Media boundary

Durable execution records are execution provenance, not media authority. Provider outputs remain `RenderOutput` / `ProviderExecutionOutput`. No `GeneratedMedia` is created by Phase 20.7.

## Consequences

- live provider jobs are visible after process restart;
- provider prompt/job IDs and execution history are auditable;
- multiple Phase 19 retries produce separate durable execution identities;
- provider execution persistence no longer depends on transient native Python objects;
- Phase 20.8 can build monitoring/recovery on durable active jobs;
- Phase 20.16 can later perform restart/provider reconciliation without redefining execution identity.

## Deferred

Phase 20.7 deliberately does not implement:

- automatic restart reconciliation;
- provider polling after restart;
- durable Phase 19 resource/worker/queue/lease storage;
- Generated Media ingestion;
- technical media validation;
- execution UI;
- multi-provider routing changes.
