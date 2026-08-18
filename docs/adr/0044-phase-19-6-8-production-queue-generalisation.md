# ADR 0044 — Phase 19.6.8 ProductionQueue Generalisation

## Status

Accepted for implementation in Phase 19.6.8.

## Context

Phase 19.6.6 introduced provider-neutral ProductionTask scheduling and Phase 19.6.7 made ProductionSchedule revisions durable and explicitly human-reviewable. The existing runtime queue predates those contracts and remains render-centric: `RenderQueueEntry` requires a `job_id` and `clip_id`, and the legacy execution service operates on `RenderJob` records.

That legacy queue must remain available while execution migration continues, but it cannot be the long-term general runtime queue because ProductionTask covers image, video, voice, audio, lip-sync, quality-control, repair, assembly, mastering and delivery work.

## Decision

### 1. Introduce a provider-neutral ProductionQueue

Add `ProductionQueue`, `ProductionQueueEntry`, `ProductionQueueAttempt`, `ProductionQueueState`, and `ProductionQueueEngine` in the ProductionTask application layer.

A queue entry references:

- `task_id` — the authoritative ProductionTask;
- `resource_id` — the provider-neutral resource selected by the approved schedule;
- `task_type` — the provider-neutral work category;
- task priority, dependency identities and retry policy;
- provider-neutral runtime lifecycle and attempt information.

It does not contain `RenderJob`, `clip_id`, provider, model, workflow or ComfyUI fields.

### 2. Compile only from the current approved ProductionSchedule

`ProductionQueueCompilerService` loads the latest persisted schedule revision and requires exactly one human review decision with `APPROVED` status and the matching schedule fingerprint.

Every scheduled task must still exist, belong to the production and remain `READY` when queue compilation occurs. A stale schedule cannot silently become runtime work.

### 3. Preserve schedule provenance in the queue

The queue records the source schedule ID, revision and fingerprint. This makes the runtime queue traceable to the exact reviewed resource-allocation decision.

### 4. Reuse the established runtime lifecycle semantics

ProductionQueue uses the generic runtime states already proven by RenderQueue:

- WAITING
- READY
- CLAIMED
- RUNNING
- RETRYING
- COMPLETED
- FAILED
- CANCELLED
- BLOCKED

The new engine supports deterministic priority ordering, claiming, attempt start/completion, cancellation and task-policy retries without renderer-specific assumptions.

### 5. Keep legacy RenderQueue intact as a compatibility runtime

Phase 19.6.8 does not delete or rewrite `RenderQueue`, `RenderQueueEngine`, `RenderQueueSerializer`, legacy `RenderJob` execution, leases or provider adapters. Existing rendering continues to use that path until a later migration phase explicitly bridges or replaces it.

The new ProductionQueue is therefore the general target contract; RenderQueue remains a compatibility implementation for existing rendering.

## Consequences

Positive:

- queueing is no longer conceptually limited to video/render jobs;
- approved scheduling authority is traceable into runtime work;
- voice, audio, post-production, QC and other task types can use the same queue contract;
- task priority and retry policy flow directly into runtime queue entries;
- no provider-specific details leak into ProductionTask or ProductionSchedule authority;
- legacy execution remains stable during incremental migration.

Deferred:

- durable ProductionQueue persistence;
- queue-to-legacy RenderQueue/RenderJob execution bridging;
- automatic ProductionTask lifecycle reconciliation from ProductionQueue runtime state;
- resource lease/capacity enforcement;
- provider/executor selection;
- monitoring/UI migration to ProductionQueue.

## Compatibility

This is additive. Existing `RenderQueue` APIs and tests remain valid and available. No UI changes are made in Phase 19.6.8.
