# ADR 0067 — Phase 20.16 Restart Recovery & Provider Reconciliation

## Status

Accepted for Phase 20.16 implementation.

## Context

Phase 20.7 made provider execution jobs durable, Phase 20.8 allowed detached provider observation, and Phases 20.15–20.15.2 added Production Execution UI, governed Production Package compilation and live monitoring. After a VSCS restart, however, workers, ProductionQueue instances and execution leases are intentionally session-scoped. A durable execution may therefore still identify a real ComfyUI prompt while the newly compiled approved queue contains the corresponding ProductionTask as READY and no live lease exists.

The system must recover provider observation without pretending that the old in-memory lease survived and without resubmitting the provider prompt.

## Decision

Phase 20.16 introduces explicit restart adoption and provider reconciliation.

Recovery is permitted only when all of the following still agree:

1. the current ProductionTask exists and its authority fingerprint matches the durable execution;
2. the current human-approved ProductionSchedule compiles successfully;
3. the regenerated queue identity and queue-entry identity match the durable execution;
4. the scheduled resource and durable worker identity still agree;
5. the durable provider identity is available through the current provider composition; and
6. the provider itself still accounts for the durable native job identity in queue or history.

Provider observations classify a durable ComfyUI prompt as pending, running, completed, failed, not found or unreachable.

### Recovery lease

The previous durable lease is provenance, not current authority. Recovery therefore creates a fresh session-scoped lease with a `PRLEASE-` identity. It does not recreate or impersonate the original `PLEASE-` lease.

### Queue reconstruction

The approved ProductionQueue remains the authority source. Durable execution attempts are used only to reconstruct real attempt history already persisted for the same queue entry. Attempt numbers must be contiguous from attempt 1, earlier attempts must be terminal, and the current durable attempt remains open until provider reconciliation finishes it.

The recovered queue entry is then adopted as RUNNING under the fresh recovery lease. No provider submission occurs during this operation.

### Provider reconciliation

For active provider work, VSCS restores the transient provider handle from durable identity, acquires recovery authority and resumes current-session monitoring.

For a provider-completed execution, VSCS reconstructs the running session view, reconciles completion, discovers the provider outputs from ComfyUI history, copies them into project-managed media storage and performs the existing Generated Media ingestion path. Provider source files are not moved or deleted.

For provider failure/cancellation, VSCS reconciles the recovered queue attempt to the corresponding terminal/retry state through existing queue runtime authority.

If ComfyUI is unreachable or no longer contains the durable prompt identity, VSCS does not manufacture terminal state. The durable execution remains available for operator review/governed retry.

## Consequences

- Restart recovery does not resubmit already-authorised provider work.
- Old lease identity is never treated as live after restart.
- Current approved schedule and ProductionTask authority are revalidated before adoption.
- Live Production Monitoring can become live again after recovery because the recovered execution has current-session queue/lease authority.
- Completed provider output can be ingested after VSCS was offline.
- Orphaned/unreachable provider work remains explicitly unresolved rather than being silently failed.
- Generated Media approval, selection and ProductionTask completion governance remain unchanged.

## Out of scope

Phase 20.16 does not introduce multi-provider routing, automatic Generated Media approval/selection, distributed locking, external multi-user recovery coordination, or provider retry policy changes. Multi-provider foundation remains Phase 20.17.
