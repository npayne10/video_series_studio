# ADR 0055 — Phase 20.6 Queue → Provider Execution Integration

## Status
Accepted for implementation validation.

## Context

Phase 19 established authoritative ProductionQueue execution with worker claims, leases, attempts and retry policy. Phase 20.3 introduced provider-execution contracts, Phase 20.4 added durable provider registration/capability resolution, and Phase 20.5 added live ComfyUI execution. The remaining gap is an application service that can take READY queue work through provider submission without allowing a provider to become an independent execution authority.

A production ComfyUI API workflow supplied for VSCS uses `XorixProductionPackageLoaderV714` as its primary runtime input. Its checked-in reference value is a sample path only and must never determine which production package is executed.

## Decision

1. `ProductionQueueRuntimeService` remains the sole owner of queue claim, start, attempt, lease, completion and failure transitions.
2. Provider capability resolution occurs before queue claim. A missing/ineligible provider therefore does not consume a ProductionTask attempt.
3. If exactly one eligible provider exists it may be selected automatically. If more than one provider is eligible, the caller must explicitly select `provider_id`; Phase 20.6 introduces no hidden load-balancing policy.
4. Runtime adapter instances are registered separately from durable `ProviderRegistration` records through `ProviderExecutionAdapterRegistry`.
5. Provider submission is asynchronous. Successful submission leaves the queue entry RUNNING under its active lease. `reconcile()` renews the lease, monitors the provider and only completes/fails/cancels the queue when the provider reaches a terminal state.
6. Submission failures after queue start are reconciled through the existing Phase 19 failure/retry policy and release the lease.
7. Provider outputs remain `ProviderExecutionOutput`/`RenderOutput` descriptors. They do not become `GeneratedMedia` in Phase 20.6.
8. The supplied `Video Production Engine v7.1.4` is added as the first reference production workflow. `ProductionPackageComfyUIAdapter` injects the queue-selected `production_package` by semantic node class and title. Node ID `107` is not treated as stable architecture.
9. The production package path may be an absolute provider-local path because ComfyUI and the custom package loader run outside VSCS project-relative media storage. It must be nonblank; durable package-location governance is outside this phase.
10. Live adapter creation remains explicit. Application bootstrap is not changed to auto-submit production work.

## Execution flow

```text
READY ProductionQueue entry
    ↓ provider/resource preflight
eligible ProviderRegistration
    ↓ runtime adapter resolution
Phase 19 claim + lease
    ↓
Phase 19 start + attempt
    ↓
ProviderExecutionContext
    ↓
RenderRequest + queue-selected production_package
    ↓
ComfyUI production-package compiler
    ↓
ProviderExecutionRequest
    ↓
Live provider submit
    ↓
RUNNING queue + active lease
    ↓ reconcile/heartbeat
provider completion/failure/cancellation
    ↓
Phase 19 terminal/retry transition
```

## Consequences

- Provider execution cannot bypass scheduling/review/queue governance.
- Multi-provider ambiguity is visible rather than silently resolved.
- Long-running provider jobs remain lease-protected while asynchronous.
- Provider execution jobs are still transient; durable execution job/attempt records are Phase 20.7.
- Provider monitoring and recovery remain minimal; broader recovery policy is Phase 20.8.
- Generated Media ingestion remains Phase 20.9.

## Deferred

- durable provider execution jobs and attempt history;
- restart reconciliation against ComfyUI history;
- provider load balancing/priority routing;
- workflow/model health discovery;
- Generated Media ingestion and validation;
- execution UI.
