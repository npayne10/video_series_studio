# ADR 0052 — Phase 20.3 Provider Execution Contract Modernisation

## Status

Accepted for implementation; local validation pending.

## Context

Phase 19 established the provider-neutral production authority used by VSCS vNext:
ProductionTask, approved ProductionSchedule, ProductionQueue, runtime workers, claims,
execution leases, attempts, retries, monitoring and recovery.

Earlier VSCS rendering work already provides useful renderer-neutral contracts such as
RenderRequest, CompiledRenderRequest, RenderAdapter, RenderJob and RenderOutput. It also
contains an older synchronous ProductionExecutor/RenderQueue execution path. That older
path predates the Phase 19 ProductionQueue and must not become a second authority for
Phase 20 live production.

Phase 20 requires a stable boundary between governed orchestration and live provider
execution while preserving existing rendering adapters and avoiding provider details in
ProductionTask or ProductionQueue authority.

## Decision

Introduce a provider-neutral execution contract in
`vscs.application.provider_execution`.

The contract contains:

- `ProviderExecutionContext` — immutable binding to one Phase 19 running queue attempt;
- `ProviderExecutionRequest` — governed execution envelope carrying a typed provider
  payload;
- `ProviderExecutionHandle` — transient provider job state;
- `ProviderExecutionOutput` — provider output descriptor before Generated Media ingestion;
- `ProviderExecutionAdapter` — validate, submit, monitor, cancel and fetch-output lifecycle;
- `ProviderExecutionContextFactory` — validates queue/task/lease/worker/attempt authority;
- `RenderProviderExecutionCompiler` and `RenderProviderExecutionAdapter` — compatibility
  bridge to the existing RenderAdapter contract.

Provider execution context may be created only when the ProductionQueue entry is
`RUNNING`, has an active attempt, and the supplied execution lease matches the queue,
entry, task and worker claim. Provider adapters therefore cannot claim or start production
work independently.

## Authority Boundary

The authoritative flow is:

```text
ProductionTask
    -> ProductionQueue
    -> worker claim
    -> execution lease
    -> RUNNING queue attempt
    -> ProviderExecutionContext
    -> ProviderExecutionRequest
    -> provider adapter
```

Provider state never becomes ProductionQueue authority by itself. Later Phase 20
integration services will reconcile provider outcomes back through the Phase 19 runtime
services.

## Existing Rendering Compatibility

The existing `RenderAdapter` contract remains valid. A rendering provider can be wrapped
by `RenderProviderExecutionAdapter`; existing `RenderJob` state is mapped to
provider-neutral `ProviderExecutionState`, and `RenderOutput` is mapped to
`ProviderExecutionOutput`.

`ProviderExecutionOutput` is not `GeneratedMedia`. Generated Media authority is created
only by the later ingestion boundary defined for Phase 20.9.

## Legacy ProductionExecutor Path

The existing synchronous `ProductionExecutor`, `ExecutionRequest`, `ExecutionResult`,
legacy `RenderQueue`, and `RenderExecutionService` are not removed in Phase 20.3 because
existing tests and compatibility paths may still depend on them.

They are not the authority for new Phase 20 provider integrations. New live providers
must integrate through the Phase 19 ProductionQueue/runtime boundary and the Phase 20
ProviderExecution contract.

## Provider Identity

`ProviderExecutionAdapter.provider_id` is a stable execution identity carried by handles
and provenance. Phase 20.3 does not define provider configuration, endpoint persistence,
health state, secrets or provider/resource matching. Those belong to Phase 20.4.

## Persistence

Provider execution handles are intentionally transient in Phase 20.3. Durable provider
jobs, attempts and restart recovery are introduced in Phases 20.7 and 20.16.

The opaque `native_handle` field exists only to bridge current adapters until durable
provider job records exist. It is not production authority and must not be serialized as
Generated Media or task governance.

## Consequences

- Phase 19 remains the sole owner of work claims, leases, attempts and retries.
- Existing RenderAdapter implementations can be reused without redesign.
- Provider-specific payloads remain outside ProductionTask and ProductionQueue authority.
- RenderOutput remains an execution output; GeneratedMedia remains the VSCS media authority.
- Live ComfyUI execution can be added in Phase 20.5 without changing the Phase 19 domain.
- Queue-to-provider orchestration remains deferred to Phase 20.6.

## Deferred

- provider registry/configuration/capability binding — Phase 20.4;
- live ComfyUI submission — Phase 20.5;
- ProductionQueue-to-provider orchestration — Phase 20.6;
- durable provider jobs/attempt history — Phase 20.7;
- live monitoring/recovery — Phase 20.8;
- Generated Media ingestion — Phase 20.9;
- restart provider reconciliation — Phase 20.16.
